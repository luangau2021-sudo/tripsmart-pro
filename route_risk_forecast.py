"""
core/route_risk_forecast.py
────────────────────────────
Module trung gian: "dự báo rủi ro theo hành trình".

Luồng:
    Tuyến đường
    → sample_route_points()        : chia tuyến thành các điểm cách nhau ~step_km
    → estimate_eta_for_points()    : ước tính thời gian đi qua từng điểm
    → analyze_route_risk_by_time() : lấy feature rủi ro + thời tiết tại ETA,
                                      gọi AI model, trả về danh sách đoạn + mức rủi ro

Hàm chính dùng trong app.py:
    analyze_route_risk_by_time(route_coords, total_duration_seconds, departure_dt,
                                risk_engine, ml_model, weather_api)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from utils.helpers import haversine_distance
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Màu hiển thị theo mức rủi ro
LEVEL_COLOR = {
    "low": "#1a73e8",        # Xanh: an toàn
    "medium": "#fdd835",     # Vàng: cần chú ý
    "high": "#fb8c00",       # Cam/Đỏ: rủi ro cao
    "very_high": "#b71c1c",  # Đỏ đậm: rủi ro rất cao
    "unknown": "#9e9e9e",     # Xám: dự báo quá xa, độ tin cậy thấp
}

LEVEL_LABEL = {
    "low": "An toàn",
    "medium": "Cần chú ý",
    "high": "Rủi ro cao",
    "very_high": "Rủi ro rất cao",
    "unknown": "Dự báo xa, độ tin cậy thấp",
}

LEVEL_ICON = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "very_high": "🔴",
    "unknown": "⚪",
}

# Quá khoảng thời gian này (giờ) thì coi dự báo thời tiết không còn đáng tin
WEATHER_FORECAST_HORIZON_HOURS = 48


# ─────────────────────────────────────────────────────────────────────────────
# 1. CHIA TUYẾN THÀNH CÁC ĐIỂM CÁCH NHAU step_km
# ─────────────────────────────────────────────────────────────────────────────
def sample_route_points(route_coords: List, step_km: float = 30.0, max_points: int = 30) -> List[Dict]:
    """
    Chia tuyến đường thành các điểm cách nhau khoảng step_km.

    Tham số:
        route_coords : list toạ độ polyline dạng [lon, lat] (theo chuẩn OSRM/GeoJSON)
        step_km      : khoảng cách giữa các điểm lấy mẫu (km)
        max_points   : số điểm tối đa (tránh quá nhiều khi tuyến rất dài)

    Trả về: list[{"lat", "lon", "route_km"}]
        Luôn bao gồm điểm đầu (route_km=0) và điểm cuối của tuyến.
    """
    if not route_coords or len(route_coords) < 2:
        return []

    result = []
    accumulated = 0.0
    next_take = 0.0
    prev = None

    for coord in route_coords:
        lon, lat = coord[0], coord[1]
        if prev is not None:
            accumulated += haversine_distance(prev[1], prev[0], lat, lon)
        if accumulated >= next_take or not result:
            result.append({"lat": lat, "lon": lon, "route_km": round(accumulated, 2)})
            next_take += step_km
        prev = coord

    # Đảm bảo có điểm cuối cùng của tuyến
    last_lon, last_lat = route_coords[-1][0], route_coords[-1][1]
    if not result or (result[-1]["lat"], result[-1]["lon"]) != (last_lat, last_lon):
        result.append({"lat": last_lat, "lon": last_lon, "route_km": round(accumulated, 2)})

    # Giới hạn số điểm nếu tuyến quá dài
    if len(result) > max_points:
        step = max(1, len(result) // max_points)
        sampled = result[::step]
        if sampled[-1] != result[-1]:
            sampled.append(result[-1])
        result = sampled

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. ƯỚC TÍNH ETA CHO TỪNG ĐIỂM
# ─────────────────────────────────────────────────────────────────────────────
def estimate_eta_for_points(
    route_points: List[Dict],
    total_duration_seconds: float,
    departure_dt: datetime,
) -> List[Dict]:
    """
    Ước tính thời gian người dùng đi qua từng điểm, dựa trên tỉ lệ
    route_km / tổng khoảng cách tuyến (giả định tốc độ trung bình không đổi).

    Trả về: list[{"lat", "lon", "route_km", "eta", "eta_text"}]
    """
    if not route_points:
        return []

    total_km = route_points[-1]["route_km"] or 1e-6
    out = []
    for p in route_points:
        frac = (p["route_km"] / total_km) if total_km > 0 else 0.0
        frac = min(1.0, max(0.0, frac))
        eta = departure_dt + timedelta(seconds=total_duration_seconds * frac)
        out.append({
            **p,
            "eta": eta,
            "eta_text": eta.strftime("%H:%M"),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3. HÀM CHÍNH: PHÂN TÍCH RỦI RO TUYẾN THEO THỜI GIAN
# ─────────────────────────────────────────────────────────────────────────────
def analyze_route_risk_by_time(
    route_coords: List,
    total_duration_seconds: float,
    departure_dt: datetime,
    risk_engine,
    ml_model,
    weather_api=None,
    step_km: float = 30.0,
    max_points: int = 20,
) -> Dict:
    """
    Hàm chính:
      - Chia tuyến thành các điểm cách nhau step_km
      - Tính ETA từng điểm
      - Lấy feature rủi ro địa lý (risk_engine) + thời tiết dự báo tại ETA (weather_api)
      - Gọi AI model (ml_model.predict_route_point_risk)
      - Trả về danh sách đoạn + mức rủi ro tổng thể

    Tham số:
        route_coords            : polyline [lon, lat] của tuyến
        total_duration_seconds  : tổng thời gian di chuyển (giây), từ router
        departure_dt            : datetime giờ xuất phát
        risk_engine             : instance RiskEngine (đã có extract_risk_features_for_point)
        ml_model                : instance MLRiskModel (đã có predict_route_point_risk)
        weather_api             : instance WeatherAPI (tuỳ chọn — nếu None, bỏ qua thời tiết)
        step_km                 : khoảng cách giữa các điểm lấy mẫu (km)
        max_points              : số điểm tối đa lấy mẫu

    Trả về dict:
        segments        : list[{
                              lat, lon, route_km, eta, eta_text,
                              level, score, geo_score, weather_score,
                              label, color, icon,
                              weather_alerts, hazard_label, hazard_type,
                              confidence,
                          }]
        overall_level   : mức rủi ro tổng quát của toàn tuyến
        overall_score   : điểm rủi ro trung bình
        overall_label   : nhãn hiển thị
        attention_segments : các đoạn cần chú ý (medium/high/very_high), sắp theo độ ưu tiên
        summary         : chuỗi tóm tắt tiếng Việt
        recommendations : list gợi ý
    """
    points = sample_route_points(route_coords, step_km=step_km, max_points=max_points)
    if not points:
        return {
            "segments": [],
            "overall_level": "unknown",
            "overall_score": 0.0,
            "overall_label": "Không có dữ liệu tuyến đường.",
            "attention_segments": [],
            "summary": "Không có dữ liệu tuyến đường.",
            "recommendations": [],
        }

    points_with_eta = estimate_eta_for_points(points, total_duration_seconds, departure_dt)

    segments = []
    now = datetime.now()

    for p in points_with_eta:
        lat, lon, eta = p["lat"], p["lon"], p["eta"]

        # ── Feature rủi ro địa lý ──────────────────────────────────────
        hazard_features = {}
        try:
            hazard_features = risk_engine.extract_risk_features_for_point(lat, lon)
        except Exception as e:
            logger.warning(f"extract_risk_features_for_point lỗi tại ({lat},{lon}): {e}")

        # ── Thời tiết dự báo tại thời điểm ETA ─────────────────────────
        weather_data = None
        weather_alerts = []
        forecast_too_far = False
        if weather_api is not None:
            try:
                hours_ahead = (eta - now).total_seconds() / 3600.0
                if hours_ahead > WEATHER_FORECAST_HORIZON_HOURS:
                    forecast_too_far = True
                else:
                    weather_data = get_weather_forecast_at_time(weather_api, lat, lon, eta)
                    weather_alerts = weather_data.get("alerts", []) if weather_data else []
            except Exception as e:
                logger.warning(f"Lấy thời tiết lỗi tại ({lat},{lon}, eta={eta}): {e}")

        # ── Gọi AI model ────────────────────────────────────────────────
        try:
            pred = ml_model.predict_route_point_risk(
                lat=lat, lon=lon, eta_time=eta,
                weather_data=weather_data, hazard_features=hazard_features,
            )
        except Exception as e:
            logger.warning(f"predict_route_point_risk lỗi tại ({lat},{lon}): {e}")
            pred = {"level": "unknown", "score": 0.0, "geo_score": 0.0,
                    "weather_score": 0.0, "label": "Không xác định",
                    "confidence": 0.0, "error": str(e)}

        level = "unknown" if forecast_too_far else pred.get("level", "low")

        segments.append({
            "lat": lat,
            "lon": lon,
            "route_km": p["route_km"],
            "eta": eta,
            "eta_text": p["eta_text"],
            "level": level,
            "score": pred.get("score", 0.0),
            "geo_score": pred.get("geo_score", 0.0),
            "weather_score": pred.get("weather_score", 0.0),
            "label": LEVEL_LABEL.get(level, "Không xác định"),
            "color": LEVEL_COLOR.get(level, LEVEL_COLOR["unknown"]),
            "icon": LEVEL_ICON.get(level, LEVEL_ICON["unknown"]),
            "weather_alerts": weather_alerts,
            "hazard_label": hazard_features.get("nearest_label"),
            "hazard_type": hazard_features.get("nearest_type"),
            "confidence": pred.get("confidence", 0.0),
        })

    return _build_summary(segments)


# ─────────────────────────────────────────────────────────────────────────────
# 4. THỜI TIẾT THEO TỌA ĐỘ + THỜI ĐIỂM
# ─────────────────────────────────────────────────────────────────────────────
def get_weather_forecast_at_time(weather_api, lat: float, lon: float, eta_time: datetime) -> Dict:
    """
    Lấy dự báo thời tiết tại (lat, lon) vào thời điểm eta_time, trả về dict
    có dạng giống get_weather_risk() của WeatherAPI:
        {"risk_score": float, "alerts": [...], "weather": {...}}

    Cách hoạt động:
      - Nếu eta_time gần hiện tại (< 2h) → dùng get_weather_risk() (thời tiết hiện tại).
      - Nếu eta_time ở tương lai → lấy get_forecast(), tìm bản ghi forecast gần nhất
        với eta_time và đánh giá rủi ro dựa trên bản ghi đó.
    """
    now = datetime.now()
    hours_ahead = (eta_time - now).total_seconds() / 3600.0

    if hours_ahead <= 2:
        try:
            return weather_api.get_weather_risk(lat, lon)
        except Exception as e:
            logger.warning(f"get_weather_risk lỗi: {e}")
            return {"risk_score": 0.0, "alerts": [], "weather": {}}

    # Lấy forecast nhiều ngày, tìm bản ghi gần ETA nhất
    days_needed = max(1, min(5, int(hours_ahead // 24) + 2))
    try:
        forecast = weather_api.get_forecast(lat, lon, days=days_needed)
    except Exception as e:
        logger.warning(f"get_forecast lỗi: {e}")
        forecast = []

    if not forecast:
        return {"risk_score": 0.0, "alerts": [], "weather": {}}

    best_item = None
    best_diff = None
    for item in forecast:
        dt_str = item.get("datetime", "")
        item_dt = _parse_forecast_datetime(dt_str)
        if item_dt is None:
            continue
        diff = abs((item_dt - eta_time).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_item = item

    if best_item is None:
        return {"risk_score": 0.0, "alerts": [], "weather": {}}

    return _weather_item_to_risk(best_item)


def _parse_forecast_datetime(dt_str: str) -> Optional[datetime]:
    """Parse chuỗi datetime trả về từ OpenWeather ('YYYY-MM-DD HH:MM:SS') hoặc Open-Meteo ('YYYY-MM-DDTHH:MM')."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def _weather_item_to_risk(item: Dict) -> Dict:
    """
    Đánh giá rủi ro thời tiết từ một bản ghi forecast (giống logic
    WeatherAPI.get_weather_risk nhưng áp dụng cho dữ liệu forecast).
    """
    alerts = []
    risk = 0.1

    condition = str(item.get("condition_main", "")).lower()
    desc = str(item.get("description", "")).lower()
    rain_mm = float(item.get("rain_mm", 0) or 0)

    if "thunderstorm" in condition or "dông" in desc:
        risk = 0.9
        alerts.append("⛈️ Dự báo dông bão — hạn chế di chuyển")
    elif "rain" in condition or "mưa" in desc or rain_mm > 0:
        if rain_mm >= 8:
            risk = 0.75
            alerts.append("🌧️ Dự báo mưa lớn — nguy cơ ngập, trơn trượt")
        elif rain_mm >= 2:
            risk = 0.55
            alerts.append("🌧️ Dự báo mưa vừa — giảm tốc độ")
        else:
            risk = 0.35
            alerts.append("🌦️ Dự báo có mưa nhẹ")

    if condition in ("fog", "mist", "haze") or "sương" in desc:
        risk = max(risk, 0.5)
        alerts.append("🌫️ Dự báo sương mù — giảm tầm nhìn")

    return {"risk_score": round(risk, 2), "alerts": alerts, "weather": item}


# ─────────────────────────────────────────────────────────────────────────────
# 5. TỔNG HỢP KẾT QUẢ
# ─────────────────────────────────────────────────────────────────────────────
_LEVEL_SCORE_FOR_AVG = {"low": 0.15, "medium": 0.5, "high": 0.75, "very_high": 0.95, "unknown": None}


def _build_summary(segments: List[Dict]) -> Dict:
    known_segments = [s for s in segments if s["level"] != "unknown"]

    scores = [s["score"] for s in known_segments] or [0.0]
    avg_score = sum(scores) / len(scores)

    if avg_score < 0.30:
        overall_level = "low"
    elif avg_score < 0.55:
        overall_level = "medium"
    elif avg_score < 0.80:
        overall_level = "high"
    else:
        overall_level = "very_high"

    overall_label = LEVEL_LABEL.get(overall_level, "Không xác định")

    # Đoạn cần chú ý: medium/high/very_high, ưu tiên theo score giảm dần
    attention = [s for s in segments if s["level"] in ("medium", "high", "very_high")]
    attention = sorted(attention, key=lambda x: x["score"], reverse=True)

    n_unknown = len(segments) - len(known_segments)

    summary_parts = [f"Tổng rủi ro tuyến: {overall_label} (TB {avg_score:.0%})"]
    if attention:
        summary_parts.append(f"{len(attention)} đoạn cần chú ý")
    if n_unknown:
        summary_parts.append(f"{n_unknown} đoạn dự báo xa, độ tin cậy thấp")
    summary = " · ".join(summary_parts)

    recommendations = []
    high_risk = [s for s in attention if s["level"] in ("high", "very_high")]
    if high_risk:
        recommendations.append("Cân nhắc đổi giờ xuất phát để tránh thời điểm rủi ro cao tại các đoạn được đánh dấu đỏ/cam.")
        if any(s["weather_alerts"] for s in high_risk):
            recommendations.append("Hạn chế đi qua đoạn rủi ro cao khi có mưa lớn hoặc dông theo dự báo.")
    if n_unknown:
        recommendations.append("Các đoạn xa (dự báo > 48h) sẽ được cập nhật chính xác hơn gần thời điểm xuất phát.")
    if not recommendations:
        recommendations.append("Tuyến đường hiện tại không có cảnh báo đáng kể — vẫn nên kiểm tra lại trước khi khởi hành.")

    return {
        "segments": segments,
        "overall_level": overall_level,
        "overall_score": round(avg_score, 3),
        "overall_label": overall_label,
        "attention_segments": attention,
        "summary": summary,
        "recommendations": recommendations,
    }