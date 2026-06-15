import streamlit as st
try:
    from streamlit_js_eval import get_geolocation
    _JSEVAL_OK = True
except ImportError:
    _JSEVAL_OK = False
import streamlit.components.v1 as components
import sys, os, folium, json

# ── Live Navigation (tích hợp vào phần Tìm đường) ───────────────────────────
try:
    from live_navigation import render_live_navigation
    _LIVE_NAV_OK = True
except ImportError:
    _LIVE_NAV_OK = False
from datetime import datetime, date, time, timedelta
EMOTION_LABELS = {1:"😞",2:"😐",3:"😊",4:"😄",5:"🤩"}
st.set_page_config(page_title="TripSmart Pro", page_icon="🗺️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Be Vietnam Pro',sans-serif;}
section[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#0f2027 0%,#203a43 50%,#2c5364 100%);}
section[data-testid="stSidebar"] *{color:white!important;}
.alert-danger {background:#ff4b4b18;border-left:4px solid #ff4b4b;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-warning{background:#ffa50018;border-left:4px solid #ffa500;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-success{background:#21c35418;border-left:4px solid #21c354;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-info   {background:#1a73e818;border-left:4px solid #1a73e8;border-radius:8px;padding:10px 14px;margin:5px 0;}
.step-box     {background:#f0f4ff;border-radius:8px;padding:8px 14px;margin:4px 0;
               border-left:3px solid #2a5298;font-size:.88rem;}
.summary-bar  {background:linear-gradient(90deg,#1a1a2e,#16213e);color:white;
               border-radius:10px;padding:12px 18px;margin:8px 0;font-size:.9rem;}
.legend-grad  {display:flex;align-items:center;gap:8px;font-size:.82rem;margin:6px 0;}
.grad-bar     {height:14px;width:220px;border-radius:7px;
               background:linear-gradient(to right,#1a73e8,#43a047,#fdd835,#fb8c00,#b71c1c);}
.reroute-box  {background:#fff8e1;border:2px solid #ffa500;border-radius:12px;padding:14px;margin:10px 0;}
.compare-table{width:100%;border-collapse:collapse;font-size:.88rem;margin:10px 0;}
.compare-table th{background:#1a1a2e;color:white;padding:10px 12px;text-align:center;font-weight:600;}
.compare-table td{padding:9px 12px;text-align:center;border-bottom:1px solid #e8eaf0;vertical-align:middle;}
.compare-table tr:hover td{background:#f5f7ff;}
.tag-fastest {background:#fff3e0;border:2px solid #ff9800;border-radius:20px;padding:3px 10px;font-weight:700;color:#e65100;white-space:nowrap;}
.tag-safest  {background:#e8f5e9;border:2px solid #43a047;border-radius:20px;padding:3px 10px;font-weight:700;color:#1b5e20;white-space:nowrap;}
.tag-balanced{background:#e3f2fd;border:2px solid #1976d2;border-radius:20px;padding:3px 10px;font-weight:700;color:#0d47a1;white-space:nowrap;}
.tag-other   {background:#f3f4f6;border:2px solid #9e9e9e;border-radius:20px;padding:3px 10px;font-weight:600;color:#555;white-space:nowrap;}
.risk-low    {color:#2e7d32;font-weight:700;}
.risk-mid    {color:#f57c00;font-weight:700;}
.risk-high   {color:#c62828;font-weight:700;}
.compare-winner{background:linear-gradient(90deg,#fffde7,#fff9c4);border-left:4px solid #ffc107;}
/* GPS IoT widget */
.iot-panel{border-radius:16px;padding:20px 24px;margin:10px 0;transition:all .3s;}
.iot-safe   {background:#f1f8e9;border:2.5px solid #43a047;}
.iot-warning{background:#fffde7;border:2.5px solid #f9a825;}
.iot-danger {background:#fff5f5;border:2.5px solid #e53935;}
.iot-led{width:56px;height:56px;border-radius:50%;flex-shrink:0;transition:background .4s,box-shadow .4s;}
.iot-led-safe   {background:#43a047;box-shadow:0 0 22px #43a047;}
.iot-led-warning{background:#f9a825;box-shadow:0 0 22px #f9a825;}
.iot-led-danger {background:#e53935;box-shadow:0 0 28px #e53935;}
.gps-badge{display:inline-flex;align-items:center;gap:6px;background:#e3f2fd;
           border:1.5px solid #1976d2;border-radius:20px;padding:4px 12px;font-size:.82rem;font-weight:600;}
.gps-dot{width:9px;height:9px;border-radius:50%;background:#1976d2;animation:gpspulse 1.4s infinite;}
@keyframes gpspulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.4)}}
</style>""", unsafe_allow_html=True)

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.routing         import Router
    from core.risk_engine     import RiskEngine
    from core.human_aware     import HumanAwareRouter
    from core.reroute         import RerouteEngine
    from features.sos         import SOSHandler
    from features.crowdsource import CrowdsourceEngine
    from features.poi         import POIEngine
    from features.memory_trail   import MemoryTrailEngine
    from features.disaster_route import DisasterRouteEngine
    from api.weather_api import WeatherAPI
    from api.maps_api    import MapsAPI
    from api.ai_engine   import AIEngine
    from core.route_risk_forecast import analyze_route_risk_by_time
    MODULES_OK = True
except Exception as e:
    MODULES_OK = False; IMPORT_ERROR = str(e)

@st.cache_resource
def init_engines():
    return (Router(), RiskEngine(), HumanAwareRouter(),
            SOSHandler(), CrowdsourceEngine(), POIEngine(),
            MemoryTrailEngine(), WeatherAPI(), MapsAPI(), AIEngine())

def risk_color(s):
    return "🔴" if s >= 0.7 else "🟡" if s >= 0.4 else "🟢"


import math

def _haversine_km(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay (km) giữa 2 toạ độ."""
    R = 6371.0
    rl = math.radians
    dlat = rl(lat2 - lat1); dlon = rl(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(rl(lat1))*math.cos(rl(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _find_nearest_segment(gps_lat, gps_lon, polyline):
    """
    Trả về dict: {segment_idx, lat, lon, dist_km, progress_ratio}
    polyline: list [[lon, lat], ...]  (OSRM format — lon trước)
    """
    best_idx, best_dist = 0, 999.0
    for i, pt in enumerate(polyline):
        lon_p, lat_p = pt[0], pt[1]
        d = _haversine_km(gps_lat, gps_lon, lat_p, lon_p)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return {
        "segment_idx"    : best_idx,
        "lat"            : polyline[best_idx][1],
        "lon"            : polyline[best_idx][0],
        "dist_km"        : round(best_dist, 3),
        "progress_ratio" : best_idx / max(1, len(polyline) - 1),
    }


def _calc_iot_state_from_gps(gps_lat, gps_lon, danger_markers, total_km):
    """
    Tính trạng thái IoT (safe/warning/danger) dựa trên GPS thật.
    danger_markers: list dict có keys lat,lon,score,route_km,label,...
    Trả về dict trạng thái đầy đủ.
    """
    # Tìm điểm nguy hiểm gần nhất (theo tọa độ thật)
    nearest_danger = None
    nearest_dist   = 999.0
    for seg in danger_markers:
        seg_lat = seg.get("lat") or seg.get("center_lat")
        seg_lon = seg.get("lon") or seg.get("center_lon")
        if seg_lat is None or seg_lon is None:
            continue
        d = _haversine_km(gps_lat, gps_lon, seg_lat, seg_lon)
        if d < nearest_dist:
            nearest_dist   = d
            nearest_danger = seg

    # Điểm nguy hiểm phía trước (dùng route_km nếu không có tọa độ)
    next_danger  = None
    next_danger_dist = 999.0
    for seg in sorted(danger_markers, key=lambda x: x.get("route_km", 0)):
        seg_lat = seg.get("lat") or seg.get("center_lat")
        seg_lon = seg.get("lon") or seg.get("center_lon")
        if seg_lat and seg_lon:
            d = _haversine_km(gps_lat, gps_lon, seg_lat, seg_lon)
            if d > 0.05:   # Bỏ qua điểm đang đứng trên nó
                next_danger      = seg
                next_danger_dist = d
                break

    cur_score = float(nearest_danger.get("score", 0)) if nearest_danger and nearest_dist < 1.0 else 0.0

    if cur_score >= 0.60 or nearest_dist < 0.5:
        state = "danger"
    elif cur_score >= 0.35 or nearest_dist < 2.0:
        state = "warning"
    elif next_danger_dist < 5.0:
        state = "warning"
    else:
        state = "safe"

    return {
        "state"           : state,
        "nearest_danger"  : nearest_danger,
        "nearest_dist"    : round(nearest_dist, 2),
        "next_danger"     : next_danger,
        "next_danger_dist": round(next_danger_dist, 2),
        "cur_score"       : cur_score,
    }


def _build_gps_component_html(interval_ms: int = 5000) -> str:
    """
    Trả về HTML nhúng component JS:
    - Hỏi quyền GPS 1 lần
    - Cập nhật tự động theo interval_ms
    - Ghi tọa độ vào localStorage key 'tripsmart_gps'
    - Hiển thị badge trạng thái GPS nhỏ gọn
    - Dùng postMessage để gửi toạ độ lên Streamlit parent frame
    """
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;padding:6px;font-family:'Segoe UI',sans-serif;background:transparent;}}
  #gps-box{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
  .badge{{display:inline-flex;align-items:center;gap:6px;border-radius:20px;
          padding:5px 14px;font-size:.82rem;font-weight:600;border:1.5px solid;}}
  .badge-ok   {{background:#e3f2fd;border-color:#1976d2;color:#1565c0;}}
  .badge-warn {{background:#fff3e0;border-color:#f57c00;color:#e65100;}}
  .badge-err  {{background:#ffebee;border-color:#e53935;color:#b71c1c;}}
  .dot{{width:9px;height:9px;border-radius:50%;animation:pulse 1.4s infinite;}}
  .dot-blue  {{background:#1976d2;}}
  .dot-orange{{background:#f57c00;}}
  .dot-red   {{background:#e53935;}}
  @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.4;transform:scale(1.5)}}}}
  #coords{{font-size:.78rem;color:#555;margin-top:2px;}}
  #btn-gps{{padding:6px 16px;background:#1976d2;color:white;border:none;
            border-radius:20px;cursor:pointer;font-size:.82rem;font-weight:600;}}
  #btn-gps:hover{{background:#1565c0;}}
</style>
</head>
<body>
<div id="gps-box">
  <button id="btn-gps" onclick="requestGPS()">📡 Bật GPS tự động</button>
  <span id="badge-area"></span>
</div>
<div id="coords"></div>

<script>
const INTERVAL_MS = {interval_ms};
let watchId = null;
let permitted = false;

function setBadge(cls, dot, text) {{
  document.getElementById('badge-area').innerHTML =
    `<span class="badge ${{cls}}"><span class="dot ${{dot}}"></span>${{text}}</span>`;
}}

function sendPos(lat, lon, acc) {{
  const payload = {{lat, lon, acc, ts: Date.now()}};
  // Gửi lên Streamlit qua postMessage
  window.parent.postMessage({{type: 'tripsmart_gps', payload}}, '*');
  // Lưu localStorage để iframe khác đọc
  try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(payload)); }} catch(e) {{}}
  document.getElementById('coords').textContent =
    `📍 Lat: ${{lat.toFixed(6)}}  Lon: ${{lon.toFixed(6)}}  ±${{acc ? acc.toFixed(0) : '?'}}m`;
}}

function onPos(pos) {{
  setBadge('badge-ok','dot-blue','GPS đang hoạt động');
  sendPos(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
}}

function onErr(err) {{
  setBadge('badge-err','dot-red', err.code === 1 ? 'Bị từ chối quyền GPS' : 'Không lấy được GPS');
}}

function requestGPS() {{
  if (!navigator.geolocation) {{
    setBadge('badge-err','dot-red','Trình duyệt không hỗ trợ GPS');
    return;
  }}
  setBadge('badge-warn','dot-orange','Đang chờ quyền GPS…');
  // Lần đầu: lấy ngay
  navigator.geolocation.getCurrentPosition(onPos, onErr, {{
    enableHighAccuracy: true, timeout: 10000, maximumAge: 0
  }});
  // Sau đó theo dõi liên tục
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  watchId = navigator.geolocation.watchPosition(onPos, onErr, {{
    enableHighAccuracy: true, timeout: 10000, maximumAge: 2000
  }});
  document.getElementById('btn-gps').textContent = '🔄 GPS đang theo dõi…';
  document.getElementById('btn-gps').disabled = true;
  permitted = true;
}}

// Tự khởi động nếu đã được cấp quyền trước đó (check localStorage)
window.addEventListener('load', () => {{
  try {{
    const saved = localStorage.getItem('tripsmart_gps');
    if (saved) {{
      const p = JSON.parse(saved);
      // Nếu GPS cũ < 30 giây thì tự bật
      if (Date.now() - p.ts < 30000) {{
        requestGPS();
      }}
    }}
  }} catch(e) {{}}
}});
</script>
</body>
</html>
"""


def _get_route_duration_seconds(route: dict) -> float:
    """
    Lấy tổng thời gian di chuyển của tuyến (giây), thử nhiều nguồn vì
    cấu trúc route trả về từ Router có thể khác nhau:
      1. Các key số giây trực tiếp: duration_seconds, duration_s, duration
         (chỉ nhận nếu giá trị là số > 0)
      2. Cộng duration_min của từng step trong route["steps"]
      3. Parse chuỗi route["duration_text"] dạng "2h 30m" / "45 phút" / "1 giờ 5 phút"
    Trả về 0.0 nếu không tìm được.
    """
    import re

    # 1) Key số trực tiếp
    for key in ("duration_seconds", "duration_s", "duration"):
        val = route.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)

    # 2) Cộng từ các step
    steps = route.get("steps") or []
    total_min = 0.0
    has_step_duration = False
    for s in steps:
        dm = s.get("duration_min")
        if isinstance(dm, (int, float)):
            total_min += dm
            has_step_duration = True
    if has_step_duration and total_min > 0:
        return total_min * 60.0

    # 3) Parse duration_text, ví dụ: "2h 30m", "1 giờ 5 phút", "45 phút", "1h"
    text = str(route.get("duration_text") or "")
    if text:
        hours = 0.0
        minutes = 0.0
        h_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|giờ|g)\b", text, re.IGNORECASE)
        m_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|min|phút|p)\b", text, re.IGNORECASE)
        if h_match:
            hours = float(h_match.group(1).replace(",", "."))
        if m_match:
            minutes = float(m_match.group(1).replace(",", "."))
        if hours or minutes:
            return hours * 3600.0 + minutes * 60.0

    return 0.0


def _compute_route_forecast(polyline, route, departure_dt, risk_engine, ml_model_route, weather_api):
    """
    Tính dự báo rủi ro theo thời gian cho một polyline + route dict.
    Trả về (route_risk_forecast_dict_or_None, total_duration_seconds, warning_msg_or_None).
    Không gọi st.* — chỉ tính toán, dùng được cho cả tuyến gốc và tuyến cập nhật ETA.
    """
    if ml_model_route is None or not ml_model_route.is_ready:
        return None, 0.0, None

    total_duration_seconds = _get_route_duration_seconds(route)
    warning_msg = None
    if total_duration_seconds <= 0:
        warning_msg = (
            "⚠️ Không xác định được tổng thời gian di chuyển của tuyến — "
            "ETA dự báo rủi ro sẽ trùng giờ xuất phát cho mọi đoạn."
        )

    forecast = analyze_route_risk_by_time(
        route_coords=polyline,
        total_duration_seconds=float(total_duration_seconds or 0),
        departure_dt=departure_dt,
        risk_engine=risk_engine,
        ml_model=ml_model_route,
        weather_api=weather_api,
    )
    return forecast, total_duration_seconds, warning_msg


def _render_route_forecast(route_risk_forecast, departure_dt, title="Dự báo rủi ro theo hành trình"):
    """Hiển thị 1 block dự báo rủi ro theo thời gian (dùng chung cho tuyến gốc và tuyến cập nhật ETA)."""
    ov_level = route_risk_forecast["overall_level"]
    ov_color = {"low":"alert-success","medium":"alert-warning",
                "high":"alert-danger","very_high":"alert-danger",
                "unknown":"alert-info"}.get(ov_level, "alert-info")
    st.markdown(
        f'<div class="{ov_color}">🤖 <b>{title}:</b> '
        f'{route_risk_forecast["overall_label"]} '
        f'(điểm TB {route_risk_forecast["overall_score"]:.0%}) · '
        f'Tham chiếu giờ {departure_dt.strftime("%H:%M")}</div>',
        unsafe_allow_html=True,
    )

    attn = route_risk_forecast.get("attention_segments", [])
    if attn:
        with st.expander(f"⏱️ Đoạn cần chú ý theo thời gian ({len(attn)})", expanded=True):
            for seg in attn[:8]:
                hz_txt = f" · gần {seg['hazard_label']}" if seg.get("hazard_label") else ""
                wx_txt = " · " + "; ".join(seg["weather_alerts"]) if seg.get("weather_alerts") else ""
                st.markdown(
                    f'<div class="step-box">{seg["icon"]} '
                    f'<b>km {seg["route_km"]:.0f}</b> · ETA {seg["eta_text"]} · '
                    f'{seg["label"]} ({seg["score"]:.0%}){hz_txt}{wx_txt}</div>',
                    unsafe_allow_html=True,
                )

    for rec in route_risk_forecast.get("recommendations", []):
        st.markdown(f'<div class="alert-info">💡 {rec}</div>', unsafe_allow_html=True)


def resolve_location(txt, maps_api):
    """Dùng cho các tab không cần chọn (thời tiết, sơ tán, v.v.)."""
    if not txt: return None, None
    if "," in txt:
        try:
            p = txt.split(","); return float(p[0].strip()), float(p[1].strip())
        except: pass
    c = maps_api.geocode(txt)
    return c if c else (None, None)


def resolve_location_candidates(txt, maps_api):
    """
    Trả về danh sách ứng viên địa điểm cho txt.
    Dùng geocode_candidates() nếu maps_api hỗ trợ; fallback về geocode() đơn.
    Kết quả: list of {"name", "address", "lat", "lon"}
    """
    if not txt:
        return []
    # Tọa độ thô → trả luôn 1 kết quả
    if "," in txt:
        try:
            p = txt.split(",")
            lat, lon = float(p[0].strip()), float(p[1].strip())
            return [{"name": txt, "address": txt, "lat": lat, "lon": lon}]
        except:
            pass
    # API nhiều kết quả
    if hasattr(maps_api, "geocode_candidates"):
        try:
            results = maps_api.geocode_candidates(txt, limit=6)
            if results:
                return results
        except Exception:
            pass
    # Fallback về geocode() đơn
    c = maps_api.geocode(txt)
    if c:
        lat, lon = c
        return [{"name": txt, "address": txt, "lat": lat, "lon": lon}]
    return []


def _handle_unknown_location(label: str, name: str, maps_api, coord_key: str) -> bool:
    """
    Hiện UI hướng dẫn khi không tìm được địa danh.
    User nhập tọa độ → lưu vào user_aliases.json → lần sau tự động tìm thấy.
    Trả True nếu user đã nhập tọa độ hợp lệ và lưu thành công.
    """
    st.warning(
        f"⚠️ Không tìm thấy **{name}** trong cơ sở dữ liệu bản đồ.\n\n"
        "Địa danh nhỏ hoặc địa phương thường không có trong OSM. "
        "Bạn có thể tra tọa độ trên Google Maps rồi nhập vào đây — "
        "app sẽ **nhớ vĩnh viễn** cho lần sau."
    )
    with st.expander("📌 Cách lấy tọa độ từ Google Maps", expanded=True):
        st.markdown(
            "1. Mở **[Google Maps](https://maps.google.com)** trên điện thoại hoặc máy tính\n"
            f"2. Tìm **{name}**\n"
            "3. Bấm giữ (hoặc click chuột phải) vào đúng vị trí trên bản đồ\n"
            "4. Tọa độ dạng `11.xxx, 107.xxx` sẽ hiện ở thanh tìm kiếm — copy lại\n"
            "5. Dán vào ô bên dưới"
        )
        coord_input = st.text_input(
            f"Tọa độ của **{name}** (dán vào đây):",
            placeholder="Ví dụ: 11.4240, 107.6460",
            key=coord_key,
        )
        if coord_input:
            try:
                parts = coord_input.replace(";", ",").split(",")
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                if not (8.0 <= lat <= 23.4 and 102.1 <= lon <= 109.5):
                    st.error("❌ Tọa độ nằm ngoài lãnh thổ Việt Nam. Kiểm tra lại.")
                    return False
                if maps_api.save_user_alias(name, lat, lon):
                    st.success(
                        f"✅ Đã lưu **{name}** → ({lat:.4f}, {lon:.4f}). "
                        "Lần sau app tự tìm thấy ngay!"
                    )
                    # Lưu vào session để dùng ngay trong lần tìm đường này
                    st.session_state[f"resolved_{coord_key}"] = {"name": name, "lat": lat, "lon": lon}
                    return True
                else:
                    st.error("❌ Lưu thất bại. Kiểm tra quyền ghi file.")
            except (ValueError, IndexError):
                st.error("❌ Định dạng sai. Nhập đúng dạng `lat, lon` — ví dụ: `11.4240, 107.6460`")
    return False



def _cluster_danger_markers(markers, max_gap_km=2.0, min_score=0.45, max_items=8):
    """
    Gom nhiều điểm nguy hiểm gần nhau thành vài đoạn trọng yếu để tránh spam UI.
    Không làm mất dữ liệu gốc; chỉ dùng cho hiển thị tab/metric/map marker.
    """
    if not markers:
        return []

    def _km(x):
        try:
            return float(x.get("route_km", 0) or 0)
        except Exception:
            return 0.0

    def _score(x):
        try:
            return float(x.get("score", 0) or 0)
        except Exception:
            return 0.0

    # Chỉ giữ các điểm có rủi ro đáng chú ý. Nếu tất cả thấp hơn ngưỡng,
    # lấy tối đa vài điểm cao nhất để người dùng vẫn có thông tin tham khảo.
    significant = [m for m in markers if _score(m) >= min_score]
    if not significant:
        return sorted(markers, key=_score, reverse=True)[:min(3, max_items)]

    # Gom theo loại/nhãn để không nhập chung lũ lụt với sạt lở nếu gần nhau.
    buckets = {}
    for m in significant:
        key = (m.get("type", "risk"), m.get("label", "Vùng rủi ro"))
        buckets.setdefault(key, []).append(m)

    clusters = []
    for _, items in buckets.items():
        items = sorted(items, key=_km)
        current = [items[0]]
        for m in items[1:]:
            if _km(m) - _km(current[-1]) <= max_gap_km:
                current.append(m)
            else:
                clusters.append(current)
                current = [m]
        clusters.append(current)

    summarized = []
    for cluster in clusters:
        cluster = sorted(cluster, key=_km)
        start_km = _km(cluster[0])
        end_km = _km(cluster[-1])
        best = max(cluster, key=_score)
        max_score = _score(best)
        avg_score = sum(_score(x) for x in cluster) / max(1, len(cluster))
        length_km = max(0.0, end_km - start_km)

        # Bỏ các cụm quá nhẹ và quá ngắn để tập trung vào điểm trọng yếu.
        if max_score < min_score and length_km < 1.0:
            continue

        if end_km - start_km >= 1:
            km_text = f"km {start_km:.0f}–{end_km:.0f}"
        else:
            km_text = f"km {start_km:.0f}"

        desc = best.get("desc", "")
        if len(cluster) > 1:
            desc = f"{desc} · Gom {len(cluster)} điểm gần nhau trong đoạn {km_text}."

        item = dict(best)
        item.update({
            "score": max_score,
            "avg_score": avg_score,
            "route_km": start_km,
            "km_start": start_km,
            "km_end": end_km,
            "km_text": km_text,
            "cluster_count": len(cluster),
            "cluster_length_km": round(length_km, 1),
            "desc": desc,
            "priority": max_score * 100 + length_km * 3 + len(cluster) * 0.5,
        })
        summarized.append(item)

    summarized.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return summarized[:max_items]


# ─────────────────────────────────────────────────────────────────────────────
# MAKE MAP
# ─────────────────────────────────────────────────────────────────────────────
def make_full_map(lat1, lon1, lat2, lon2,
                  colored_segments=None,
                  route_polyline=None,
                  alt_routes=None,
                  danger_markers=None,
                  rest_suggestions=None,
                  pois=None,
                  reports=None,
                  incident_marker=None,
                  forecast_segments=None):

    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=9,
                   tiles=None, prefer_canvas=True)

    folium.TileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                     attr="© OpenStreetMap", name="🗺️ Đường phố", max_zoom=19).add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
                     attr="© Google", name="🛰️ Vệ tinh", max_zoom=20).add_to(m)

    all_lats = [lat1, lat2]
    all_lons = [lon1, lon2]

    # ── Tuyến thay thế mờ ────────────────────────────────────────────────
    ALT_COLORS = ["#90caf9", "#a5d6a7", "#ef9a9a"]
    if alt_routes:
        for i, rt in enumerate(alt_routes):
            poly = rt.get("polyline", [])
            if not poly or len(poly) < 2: continue
            coords = [[p[1], p[0]] for p in poly]
            all_lats += [p[1] for p in poly]
            all_lons += [p[0] for p in poly]
            folium.PolyLine(coords, color=ALT_COLORS[i % len(ALT_COLORS)],
                weight=4, opacity=0.25,
                tooltip=f"{rt.get('label','Tuyến thay thế')} · {rt.get('distance_text','')} · {rt.get('duration_text','')}",
                smooth_factor=0, line_cap="round", line_join="round",
            ).add_to(m)

    # ── Tuyến chính gốc từ OSRM ───────────────────────────────────────────
    # FIX: Vẽ toàn bộ polyline gốc trước để đường luôn bám đúng mặt đường thật.
    # colored_segments chỉ là lớp phủ rủi ro; không dùng nó làm hình dạng chính
    # vì nếu risk_engine lấy mẫu thưa, đường sẽ nối thẳng và nhìn như đi xuyên rừng.
    if route_polyline:
        try:
            coords = [[p[1], p[0]] for p in route_polyline if len(p) >= 2]
            if len(coords) >= 2:
                all_lats += [p[1] for p in route_polyline if len(p) >= 2]
                all_lons += [p[0] for p in route_polyline if len(p) >= 2]
                folium.PolyLine(
                    coords,
                    color="#263238",
                    weight=8,
                    opacity=0.35,
                    tooltip="Tuyến OSRM gốc — bám đường thật",
                    smooth_factor=0,
                    line_cap="round",
                    line_join="round",
                ).add_to(m)
        except Exception:
            pass

    # ── Gradient polyline chính ───────────────────────────────────────────
    # Lớp này chỉ tô màu rủi ro trên đúng tuyến, không quyết định hình dạng tuyến.
    if colored_segments:
        for seg in colored_segments:
            all_lats += [seg["lat1"], seg["lat2"]]
            all_lons += [seg["lon1"], seg["lon2"]]
            score = seg["score"]
            w = 4 + int(score * 4)
            folium.PolyLine(
                [[seg["lat1"], seg["lon1"]], [seg["lat2"], seg["lon2"]]],
                color=seg["color"], weight=w, opacity=0.92,
                tooltip=f"Rủi ro: {score:.0%} | km {seg['route_km']:.1f}",
                smooth_factor=0, line_cap="round", line_join="round",
            ).add_to(m)

    # ── Marker xuất phát / đến ───────────────────────────────────────────
    folium.Marker([lat1, lon1],
        popup=folium.Popup("<b>🟢 Điểm xuất phát</b>", max_width=160),
        tooltip="Xuất phát",
        icon=folium.Icon(color="green", icon="play", prefix="glyphicon"),
    ).add_to(m)
    folium.Marker([lat2, lon2],
        popup=folium.Popup("<b>🏁 Điểm đến</b>", max_width=160),
        tooltip="Điểm đến",
        icon=folium.Icon(color="red", icon="flag", prefix="glyphicon"),
    ).add_to(m)

    # ── Marker nguy hiểm — TOP 5, vòng tròn nhỏ gọn ─────────────────────
    # FIX: Chỉ hiện 5 điểm nguy hiểm nhất + vòng tròn bán kính cố định nhỏ
    HAZARD_COLOR = {"landslide":"red","flood":"blue","geological":"darkred","bad_road":"orange"}
    HAZARD_ICON2 = {"landslide":"ban-circle","flood":"tint","geological":"warning-sign","bad_road":"road"}
    if danger_markers:
        top5 = sorted(danger_markers, key=lambda x: x.get("score", 0), reverse=True)[:5]
        for seg in top5:
            sc    = seg.get("score", 0)
            htype = seg.get("type", "bad_road")
            fc    = HAZARD_COLOR.get(htype, "red")
            fi    = HAZARD_ICON2.get(htype, "warning-sign")
            km_txt = f"km {seg.get('route_km', 0):.0f}"
            level  = "🔴 Nguy hiểm" if sc >= 0.7 else "🟡 Chú ý"

            # Vòng tròn cố định nhỏ: 400–800m
            folium.Circle([seg["lat"], seg["lon"]], radius=int(400 + sc * 400),
                color=seg.get("color","#e53935"), fill=True,
                fill_opacity=0.15, weight=1.5).add_to(m)

            popup_html = (
                f"<div style='font-family:sans-serif;min-width:210px'>"
                f"<b>{seg.get('icon','⚠️')} {seg.get('label','')}</b><br>"
                f"<span style='background:{seg.get('color','#e53935')};color:white;"
                f"padding:2px 8px;border-radius:4px;font-size:.75rem'>"
                f"{level} · {sc:.0%}</span><br><br>"
                f"<span style='font-size:.83rem'>{seg.get('desc','')}</span><br>"
                f"<span style='color:#888;font-size:.75rem'>📍 {km_txt}</span></div>"
            )
            folium.Marker([seg["lat"], seg["lon"]],
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{seg.get('icon','⚠️')} {seg.get('label','')} ({km_txt})",
                icon=folium.Icon(color=fc, icon=fi, prefix="glyphicon"),
            ).add_to(m)

    # ── Điểm dừng nghỉ ───────────────────────────────────────────────────
    if rest_suggestions:
        for rs in rest_suggestions:
            km_txt = f"km {rs.get('route_km', 0):.0f}"
            folium.Marker([rs["lat"], rs["lon"]],
                popup=folium.Popup(
                    f"<div style='font-family:sans-serif'>"
                    f"<b style='color:#2e7d32'>{rs.get('icon','☕')} {rs.get('name','')}</b><br>"
                    f"<span style='font-size:.83rem'>{rs.get('desc','')}</span><br>"
                    f"<span style='color:#888;font-size:.75rem'>📍 {km_txt}</span></div>",
                    max_width=230),
                tooltip=f"☕ {rs.get('name','')} ({km_txt})",
                icon=folium.Icon(color="green", icon="time", prefix="glyphicon"),
            ).add_to(m)

    # ── POI dọc tuyến ────────────────────────────────────────────────────
    CSTYLE = {
        "food":("orange","cutlery"),"nature":("darkgreen","tree-conifer"),
        "scenic":("cadetblue","camera"),"culture":("purple","book"),
        "relaxation":("lightblue","tint"),"ecotourism":("darkgreen","leaf"),
        "attraction":("blue","star"),
    }
    CEMOJI = {"food":"🍜","nature":"🌿","scenic":"📸","culture":"🏛️",
              "relaxation":"🏖️","ecotourism":"🌲","attraction":"⭐"}
    if pois:
        for poi in pois:
            cat = poi.get("category","attraction")
            fc2, fi2 = CSTYLE.get(cat, ("blue","star"))
            emoji = CEMOJI.get(cat,"📍")
            km_txt = f"km {poi.get('route_km',0):.0f}"
            folium.Marker([poi["lat"], poi["lon"]],
                popup=folium.Popup(
                    f"<div style='font-family:sans-serif;min-width:190px'>"
                    f"<b>{emoji} {poi['name']}</b><br>"
                    f"<span style='font-size:.8rem;color:#555'>{poi.get('type','')} · ⭐{poi.get('rating','?')} · {poi.get('province','')}</span><br>"
                    f"<span style='color:#888;font-size:.75rem'>📍 {km_txt} · ↔️{poi.get('dist_from_route_km',0)} km</span></div>",
                    max_width=240),
                tooltip=f"{emoji} {poi['name']} ({km_txt})",
                icon=folium.Icon(color=fc2, icon=fi2, prefix="glyphicon"),
            ).add_to(m)

    # ── Báo cáo cộng đồng ────────────────────────────────────────────────
    RICON = {"accident":("red","exclamation-sign"),"flood":("blue","tint"),
             "traffic_jam":("orange","road"),"bad_road":("orange","warning-sign"),
             "landslide":("darkred","ban-circle")}
    if reports:
        for r in reports:
            c2, ic2 = RICON.get(r.get("type",""), ("gray","info-sign"))
            folium.Marker([r["lat"], r["lon"]],
                popup=folium.Popup(
                    f"<b>{r.get('icon','')} {r.get('label','')}</b><br>"
                    f"{r.get('description','')}<br>👍 {r.get('upvotes',0)}",
                    max_width=210),
                tooltip=f"{r.get('icon','')} {r.get('label','')}",
                icon=folium.Icon(color=c2, icon=ic2, prefix="glyphicon"),
            ).add_to(m)

    # ── Marker sự cố ─────────────────────────────────────────────────────
    if incident_marker:
        folium.Marker([incident_marker["lat"], incident_marker["lon"]],
            popup=folium.Popup(f"<b>🚧 Sự cố</b><br>{incident_marker.get('desc','')}", max_width=200),
            tooltip="🚧 Sự cố",
            icon=folium.Icon(color="black", icon="remove-sign", prefix="glyphicon"),
        ).add_to(m)

    # ── Dự báo rủi ro theo thời gian (AI) ─────────────────────────────────
    if forecast_segments:
        for seg in forecast_segments:
            level = seg.get("level", "low")
            if level == "low":
                continue  # bỏ qua các điểm an toàn để tránh spam bản đồ
            all_lats.append(seg["lat"])
            all_lons.append(seg["lon"])
            popup_html = (
                f"<div style='font-family:sans-serif;min-width:200px'>"
                f"<b>{seg.get('icon','⚪')} {seg.get('label','')}</b><br>"
                f"<span style='font-size:.85rem'>km {seg.get('route_km',0):.0f} · "
                f"ETA {seg.get('eta_text','')}</span><br>"
                f"<span style='font-size:.8rem'>Điểm rủi ro: {seg.get('score',0):.0%}</span>"
                + ("<br><span style='font-size:.78rem;color:#555'>"
                   + "; ".join(seg.get("weather_alerts", [])) + "</span>" if seg.get("weather_alerts") else "")
                + "</div>"
            )
            folium.CircleMarker(
                [seg["lat"], seg["lon"]],
                radius=7,
                color=seg.get("color", "#9e9e9e"),
                fill=True,
                fill_color=seg.get("color", "#9e9e9e"),
                fill_opacity=0.85,
                weight=1,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f"{seg.get('icon','⚪')} km {seg.get('route_km',0):.0f} · ETA {seg.get('eta_text','')} · {seg.get('label','')}",
            ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    pad = 0.05
    if all_lats and all_lons:
        m.fit_bounds([[min(all_lats)-pad, min(all_lons)-pad],
                      [max(all_lats)+pad, max(all_lons)+pad]])
    return m._repr_html_()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗺️ TripSmart Pro")
    st.markdown("*Human-Aware Navigation VN*")
    st.divider()
    menu = st.radio("", [
        "🗺️  Tìm đường",
        "⚠️  Kiểm tra rủi ro",
        "🆘  SOS Khẩn cấp",
        "📍  Báo cáo cộng đồng",
        "🏛️  Điểm tham quan",
        "📔  Ký ức hành trình",
        "🌪️  Sơ tán thiên tai",
        "🌤️  Thời tiết",
    ], label_visibility="collapsed")
    st.divider()
    # ── Mục kỹ thuật/admin (ẩn mặc định) ────────────────────────────────
    with st.expander("🛠️ Kỹ thuật / Admin", expanded=False):
        show_ai_admin = st.checkbox("🤖 Hiện AI Risk Model (admin)", value=False, key="show_ai_admin")
        if show_ai_admin:
            menu = "🤖  AI Risk Model"
    st.divider()
    st.markdown("**📞 Khẩn cấp**")
    st.markdown("🚓 Công an: **113**")
    st.markdown("🚒 Cứu hỏa: **114**")
    st.markdown("🚑 Cấp cứu: **115**")
    st.markdown("🏔️ Cứu nạn: **1800 599 920**")
    st.divider()
    # ── Quản lý địa danh đã lưu ────────────────────────────────────────
    if "maps_api" in dir():  # chỉ hiện sau khi init_engines() chạy
        _saved = maps_api.list_user_aliases() if hasattr(maps_api, "list_user_aliases") else []
        label = f"📌 Địa danh đã lưu ({len(_saved)})" if _saved else "📌 Địa danh đã lưu"
        with st.expander(label, expanded=False):
            if not _saved:
                st.caption("Chưa có địa danh nào. Khi tìm không thấy, app sẽ hỏi bạn nhập tọa độ và lưu lại ở đây.")
            else:
                for item in _saved:
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{item['name']}**  \n`{item['lat']:.4f}, {item['lon']:.4f}`")
                    if c2.button("🗑️", key=f"del_alias_{item['name']}", help="Xoá"):
                        maps_api.delete_user_alias(item["name"])
                        st.rerun()

if not MODULES_OK:
    st.error(f"❌ Không load được module: `{IMPORT_ERROR}`")
    st.stop()

(router, risk_engine, human_router,
 sos, crowd, poi_engine, memory,
 weather_api, maps_api, ai_engine) = init_engines()

from core.reroute         import RerouteEngine
from features.disaster_route import DisasterRouteEngine
reroute  = RerouteEngine(router, risk_engine)
disaster = DisasterRouteEngine(router, risk_engine)

# ── AI Risk Model (lazy init) ────────────────────────────────────────────────
@st.cache_resource
def init_ml_model():
    try:
        from core.ml_risk_model import MLRiskModel
        return MLRiskModel()
    except Exception as e:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TÌM ĐƯỜNG
# ═══════════════════════════════════════════════════════════════════════════════
if "Tìm đường" in menu:
    st.title("🗺️ Tìm đường thông minh")

    # ── Lấy GPS làm điểm xuất phát ──────────────────────────────────────────
    # Nếu user bấm nút, gọi get_geolocation() ngay, lưu vào session rồi rerun
    _use_my_loc = st.button(
        "📡 Dùng vị trí GPS của tôi làm điểm xuất phát",
        key="btn_use_gps_origin",
        help="Trình duyệt sẽ hỏi quyền vị trí lần đầu — chỉ hỏi 1 lần.",
    )
    if _use_my_loc:
        if _JSEVAL_OK:
            with st.spinner("📡 Đang lấy GPS…"):
                _geo_origin = get_geolocation()
            if _geo_origin and isinstance(_geo_origin, dict):
                _c = _geo_origin.get("coords", {})
                _lat_o = _c.get("latitude")
                _lon_o = _c.get("longitude")
                _acc_o = _c.get("accuracy")
                if _lat_o and _lon_o:
                    _gps_str = f"{_lat_o:.6f},{_lon_o:.6f}"
                    st.session_state["origin_from_gps"] = _gps_str
                    # Ghi thẳng vào key của text_input để điền vào ô ngay lập tức
                    st.session_state["input_origin"] = _gps_str
                    _acc_txt = f" (±{_acc_o:.0f}m)" if _acc_o else ""
                    st.success(f"✅ GPS: {_lat_o:.5f}, {_lon_o:.5f}{_acc_txt} — đã điền vào ô xuất phát.")
                else:
                    st.error("⚠️ Lấy được GPS nhưng không đọc được tọa độ.")
            else:
                st.warning("⏳ Chưa nhận được GPS. Hãy **cho phép quyền vị trí** trên trình duyệt rồi bấm lại.")
        else:
            st.error("Thiếu thư viện `streamlit-js-eval`. Chạy: `pip install streamlit-js-eval`")

    col1, col2 = st.columns(2)
    with col1:
        origin_input = st.text_input(
            "📍 Điểm xuất phát",
            placeholder="VD: TP.HCM  hoặc  10.77,106.69",
            key="input_origin",
        )
    with col2:
        dest_input = st.text_input("🏁 Điểm đến", placeholder="VD: Đà Lạt  hoặc  11.94,108.44")

    r2a, r2b, r2c, r2d = st.columns(4)
    with r2a:
        mode = st.selectbox("🚗 Phương tiện", ["car","motorbike","bike","walk"],
            format_func=lambda x:{"car":"🚗 Ô tô","motorbike":"🏍️ Xe máy",
                                   "bike":"🚲 Xe đạp","walk":"🚶 Đi bộ"}[x])
    with r2b:
        poi_style = st.selectbox("🏖️ Địa điểm dọc đường",
            ["all","food","adventure","culture","relaxation","family"],
            format_func=lambda x:{
                "all":"🌐 Tất cả","food":"🍜 Ăn uống","adventure":"🏔️ Thiên nhiên",
                "culture":"🏛️ Văn hoá","relaxation":"🏖️ Nghỉ dưỡng","family":"👨‍👩‍👧 Gia đình"}[x])
    with r2c:
        show_alt = st.checkbox("🔀 Tuyến thay thế", value=False)
    with r2d:
        departure_time = st.time_input("🕒 Giờ xuất phát", value=datetime.now().time())
        departure_dt = datetime.combine(date.today(), departure_time)

    with st.expander("👤 Human-Aware Routing"):
        h1,h2,h3 = st.columns(3)
        with h1:
            age=st.number_input("Tuổi",10,100,30)
            travel_hour=st.number_input("Giờ xuất phát",0,23,8)
        with h2:
            motion_sick=st.checkbox("Dễ say xe")
            has_children=st.checkbox("Có trẻ nhỏ")
        with h3:
            stress_level=st.slider("Mức stress",1,5,2)
        use_human=st.checkbox("✅ Bật Human-Aware",value=True)

    run_search = st.button("🔍 Tìm đường", type="primary", use_container_width=True)

    # ── Phase 1: user bấm "Tìm đường" → geocode và lưu candidates vào session ──
    if run_search:
        if not origin_input or not dest_input:
            st.warning("Nhập điểm xuất phát và điểm đến."); st.stop()

        with st.spinner("📡 Tìm địa điểm..."):
            origin_cands = resolve_location_candidates(origin_input, maps_api)
            dest_cands   = resolve_location_candidates(dest_input,   maps_api)

        if not origin_cands:
            if not _handle_unknown_location("Điểm xuất phát", origin_input, maps_api, "coord_origin"):
                st.stop()
            resolved = st.session_state.get("resolved_coord_origin")
            if not resolved: st.stop()
            origin_cands = [resolved]

        if not dest_cands:
            if not _handle_unknown_location("Điểm đến", dest_input, maps_api, "coord_dest"):
                st.stop()
            resolved = st.session_state.get("resolved_coord_dest")
            if not resolved: st.stop()
            dest_cands = [resolved]

        # Lưu vào session để phase 2 dùng sau rerun
        st.session_state["pending_origin_cands"] = origin_cands
        st.session_state["pending_dest_cands"]   = dest_cands
        # Xoá kết quả cũ khi search mới
        st.session_state.pop("last_routes", None)

    # ── Phase 2: hiện selectbox + nút Xác nhận (đọc candidates từ session) ──
    _o_cands = st.session_state.get("pending_origin_cands")
    _d_cands = st.session_state.get("pending_dest_cands")

    confirm_pressed = False
    if _o_cands and _d_cands and not st.session_state.get("last_routes"):
        needs_confirm = (len(_o_cands) > 1) or (len(_d_cands) > 1)

        if len(_o_cands) > 1:
            st.markdown("**📍 Điểm xuất phát** — Tìm thấy nhiều nơi trùng tên:")
            o_opts = [f"{c['name']} — {c.get('address','')}" for c in _o_cands]
            _oi = st.selectbox("Chọn điểm xuất phát", range(len(o_opts)),
                               format_func=lambda i: o_opts[i], key="sel_origin")
        else:
            _oi = 0

        if len(_d_cands) > 1:
            st.markdown("**🏁 Điểm đến** — Tìm thấy nhiều nơi trùng tên:")
            d_opts = [f"{c['name']} — {c.get('address','')}" for c in _d_cands]
            _di = st.selectbox("Chọn điểm đến", range(len(d_opts)),
                               format_func=lambda i: d_opts[i], key="sel_dest")
        else:
            _di = 0

        if needs_confirm:
            confirm_pressed = st.button("✅ Xác nhận và tìm đường", type="primary")
            if not confirm_pressed:
                st.info("👆 Chọn đúng địa điểm rồi bấm **Xác nhận và tìm đường**.")
                st.stop()
        else:
            confirm_pressed = True  # 1 kết quả mỗi đầu → tự xác nhận

    # ── Phase 3: tính tuyến ──────────────────────────────────────────────────
    if st.session_state.get("last_routes"):
        lat1, lon1 = st.session_state["last_origin"]
        lat2, lon2 = st.session_state["last_dest"]
        mode       = st.session_state.get("last_mode", mode)
        routes     = st.session_state.get("last_routes", [])

    elif confirm_pressed and _o_cands and _d_cands:
        _oi = st.session_state.get("sel_origin", 0)
        _di = st.session_state.get("sel_dest",   0)
        lat1 = _o_cands[_oi]["lat"];  lon1 = _o_cands[_oi]["lon"]
        lat2 = _d_cands[_di]["lat"];  lon2 = _d_cands[_di]["lon"]

        if not lat1 or not lat2:
            st.error("❌ Không lấy được tọa độ. Thử `10.77,106.69`"); st.stop()

        with st.spinner("🛣️ Tính tuyến (OSRM)..."):
            if show_alt:
                routes = router.get_alternative_routes((lat1,lon1),(lat2,lon2),mode=mode,count=3)
            else:
                r = router.get_route((lat1,lon1),(lat2,lon2),mode=mode)
                routes = [r] if r else []

        if not routes:
            st.error("❌ Không tìm được tuyến."); st.stop()

        labels = ["🚀 Nhanh nhất","⛽ Tiết kiệm","🌿 Cảnh đẹp"]
        for i, rt in enumerate(routes):
            if "label" not in rt:
                rt["label"] = labels[i] if i < len(labels) else f"Tuyến {i+1}"

        st.session_state.update({
            "last_origin": (lat1,lon1), "last_dest": (lat2,lon2),
            "last_mode": mode, "last_routes": routes,
        })

    if st.session_state.get("last_routes"):
        lat1, lon1 = st.session_state["last_origin"]
        lat2, lon2 = st.session_state["last_dest"]
        mode       = st.session_state.get("last_mode", mode)
        routes     = st.session_state.get("last_routes", [])

        selected = st.session_state.get("last_selected", 0)

        # ── BẢNG SO SÁNH TUYẾN (chỉ hiện khi có ≥2 tuyến) ─────────────────
        if len(routes) > 1:
            with st.spinner("📊 Đang so sánh các tuyến đường..."):
                compared = risk_engine.compare_routes(routes)
                st.session_state["last_compared"] = compared

            fastest  = next((r for r in compared if r.get("tag") == "fastest"),  None)
            safest   = next((r for r in compared if r.get("tag") == "safest"),   None)
            balanced = next((r for r in compared if r.get("tag") == "balanced"), None)

            # ── Thẻ gợi ý 3 cột ──────────────────────────────────────────
            hint_cols = st.columns(3)
            for col, item, css_cls in zip(
                hint_cols,
                [fastest, safest, balanced],
                ["tag-fastest", "tag-safest", "tag-balanced"],
            ):
                if not item:
                    continue
                dur_h = int(item["duration_min"] // 60)
                dur_m = int(item["duration_min"] % 60)
                dur_txt = item.get("duration_text") or (f"{dur_h}h {dur_m}p" if dur_h else f"{dur_m} phút")
                risk_pct = f"{item['avg_risk_score']:.0%}"
                risk_cls = ("risk-low" if item["avg_risk_score"] < 0.35
                            else "risk-mid" if item["avg_risk_score"] < 0.60 else "risk-high")
                col.markdown(
                    f'<div style="border-radius:12px;padding:14px 16px;'
                    f'background:#fafafa;border:1.5px solid #ddd;margin-bottom:4px">'
                    f'<div class="{css_cls}" style="display:inline-block;margin-bottom:8px">'
                    f'{item["tag_label"]}</div><br>'
                    f'<b>{item["label"]}</b><br>'
                    f'📏 {item.get("distance_text","?")} &nbsp;·&nbsp; ⏱️ {dur_txt}<br>'
                    f'<span class="{risk_cls}">Rủi ro TB: {risk_pct}</span>'
                    f' &nbsp;·&nbsp; {item["danger_count"]} vùng nguy hiểm'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Bảng chi tiết ────────────────────────────────────────────
            st.markdown("#### 📊 Bảng so sánh chi tiết tuyến đường")
            TAG_CSS = {"fastest":"tag-fastest","safest":"tag-safest",
                       "balanced":"tag-balanced","other":"tag-other"}
            rows_html = ""
            for r in compared:
                tag_css  = TAG_CSS.get(r.get("tag","other"), "tag-other")
                risk_s   = r["avg_risk_score"]
                risk_cls = ("risk-low" if risk_s < 0.35
                            else "risk-mid" if risk_s < 0.60 else "risk-high")
                risk_icon = "🟢" if risk_s < 0.35 else "🟡" if risk_s < 0.60 else "🔴"
                dur_h = int(r["duration_min"] // 60)
                dur_m = int(r["duration_min"] % 60)
                dur_txt  = r.get("duration_text") or (f"{dur_h}h {dur_m}p" if dur_h else f"{dur_m} phút")
                dist_txt = r.get("distance_text") or f"{r['distance_km']:.0f} km"
                row_cls  = "compare-winner" if r.get("tag") in ("fastest","safest","balanced") else ""
                rows_html += (
                    f'<tr class="{row_cls}">'
                    f'<td style="text-align:left;font-weight:600">{r["label"]}</td>'
                    f'<td>{dist_txt}</td>'
                    f'<td>⏱️ {dur_txt}</td>'
                    f'<td><span class="{risk_cls}">{risk_icon} {risk_s:.0%}</span></td>'
                    f'<td>{r["danger_count"]} vùng</td>'
                    f'<td><span class="{risk_cls}">{r["ai_label"]}</span></td>'
                    f'<td><span class="{tag_css}">{r["tag_label"]}</span></td>'
                    f'</tr>'
                )
            st.markdown(
                f'<table class="compare-table"><thead><tr>'
                f'<th style="text-align:left">Tuyến</th>'
                f'<th>Khoảng cách</th><th>Thời gian</th>'
                f'<th>Rủi ro TB</th><th>Vùng nguy hiểm</th>'
                f'<th>AI đánh giá</th><th>Gợi ý</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table>',
                unsafe_allow_html=True,
            )
            st.caption("💡 Chọn tuyến phù hợp với nhu cầu bên dưới.")
            st.divider()

            # ── Gợi ý mặc định thông minh ────────────────────────────────
            if "last_selected" not in st.session_state:
                _bal = next((r["route_index"] for r in compared if r.get("tag") == "balanced"), None)
                _saf = next((r["route_index"] for r in compared if r.get("tag") == "safest"),   None)
                selected = _bal if _bal is not None else (_saf or 0)

            def _fmt_route(i):
                if "last_compared" in st.session_state:
                    m = next((r for r in st.session_state["last_compared"]
                              if r["route_index"] == i), None)
                    if m:
                        return f"{m['tag_label']}  {routes[i]['label']}  ·  {routes[i].get('duration_text','?')}"
                return routes[i]["label"]

            selected = st.selectbox(
                "🗺️ Chọn tuyến để xem chi tiết",
                range(len(routes)),
                index=min(selected, len(routes) - 1),
                format_func=_fmt_route,
                key="route_selector",
            )
        else:
            selected = 0

        st.session_state["last_selected"] = selected

        route       = routes[selected]
        is_fallback = route.get("fallback", False)
        polyline    = route.get("polyline", [])

        profile = None
        if use_human:
            profile = human_router.build_profile(
                age, travel_hour, motion_sick, stress_level, has_children)
            route = human_router.adjust_route_score(route, profile)

        with st.spinner("🎨 Tô màu rủi ro từng đoạn..."):
            colored_segs = risk_engine.score_polyline_segments(polyline)

        with st.spinner("🔍 Phân tích nguy hiểm..."):
            # Nếu đã so sánh tuyến thì tái dùng kết quả — tránh tính lại
            _cmp_cache = st.session_state.get("last_compared")
            _cmp_match = next((r for r in _cmp_cache
                               if r.get("route_index") == selected), None) if _cmp_cache else None
            if _cmp_match and "danger_segments" in _cmp_match:
                analysis = {
                    "danger_segments" : _cmp_match["danger_segments"],
                    "rest_suggestions": risk_engine._suggest_rest_stops(polyline),
                    "avg_score"       : _cmp_match["avg_risk_score"],
                    "safe_to_proceed" : _cmp_match["avg_risk_score"] < 0.50,
                    "summary"         : _cmp_match.get("analysis_summary", ""),
                }
            else:
                analysis = risk_engine.analyze_route(polyline)
            danger_markers_raw = analysis.get("danger_segments",  [])
            danger_markers     = _cluster_danger_markers(
                danger_markers_raw,
                max_gap_km=2.0,
                min_score=0.45,
                max_items=8,
            )
            rest_stops         = analysis.get("rest_suggestions", [])

        with st.spinner("🤖 Dự báo rủi ro theo thời gian di chuyển..."):
            ml_model_route = init_ml_model()
            route_risk_forecast = None
            if ml_model_route is not None and ml_model_route.is_ready:
                try:
                    route_risk_forecast, _tds, warn_msg = _compute_route_forecast(
                        polyline, route, departure_dt, risk_engine, ml_model_route, weather_api,
                    )
                    if warn_msg:
                        st.warning(warn_msg)
                except Exception as e:
                    st.warning(f"⚠️ Không thể dự báo rủi ro theo thời gian: {e}")
                    route_risk_forecast = None
            else:
                st.caption("ℹ️ AI Risk Model chưa sẵn sàng — bỏ qua dự báo rủi ro theo thời gian.")

        with st.spinner("📍 Tìm địa điểm dọc đường..."):
            pois = poi_engine.get_pois_on_route(polyline, style=poi_style, buffer_km=8.0, max_results=12)

        rpts = crowd.get_nearby_reports(lat1, lon1, 60)

        # Lưu vào session cho cảnh báo IoT GPS
        st.session_state["last_danger_markers"] = danger_markers
        st.session_state["last_route_km"] = route.get("distance_km", 0)
        st.session_state["last_polyline"]  = polyline
        # Reset IoT step khi tuyến mới được chọn
        if st.session_state.get("_prev_selected") != selected:
            st.session_state["iot_step"] = 0
            st.session_state["_prev_selected"] = selected

        # Metrics
        st.success("✅ Đã tìm thấy tuyến đường!")
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("📏 Khoảng cách",       route.get("distance_text","?"))
        m2.metric("⏱️ Thời gian",         route.get("duration_text","?"))
        m3.metric("🚨 Vùng trọng yếu",    len(danger_markers),
                  delta=f"lọc từ {len(danger_markers_raw)} điểm" if len(danger_markers_raw) != len(danger_markers) else None)
        m4.metric("☕ Điểm dừng nghỉ",    len(rest_stops))
        m5.metric("📍 Địa điểm",          len(pois))

        if is_fallback:
            st.warning(f"⚠️ {route.get('note','')}  \nKiểm tra kết nối internet.")
        else:
            st.info(f"✅ Tuyến thực tế từ **OSRM** · {len(polyline)} điểm GPS")

        if profile:
            st.markdown(f'<div class="alert-info">🧠 <b>{profile["summary"]}</b></div>', unsafe_allow_html=True)
            for a in profile.get("alerts",[]):
                st.markdown(f'<div class="alert-warning">{a}</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="summary-bar">🛡️ <b>Tóm tắt:</b> &nbsp;{analysis.get("summary","")}</div>',
                    unsafe_allow_html=True)

        # ── Dự báo rủi ro theo thời gian (AI) ────────────────────────────────
        if route_risk_forecast:
            _render_route_forecast(route_risk_forecast, departure_dt, title="Dự báo rủi ro theo hành trình (kế hoạch)")

        st.markdown("""
        <div class="legend-grad">
          <span>🔵 An toàn</span><div class="grad-bar"></div><span>🔴 Nguy hiểm</span>
          &nbsp;|&nbsp; 🟢 Điểm nghỉ &nbsp;|&nbsp; 📍 POI &nbsp;|&nbsp; ⚠️ Cộng đồng
          &nbsp;|&nbsp; 🟡🟠🔴⚪ Dự báo rủi ro theo giờ đi qua
        </div>""", unsafe_allow_html=True)

        # BẢN ĐỒ
        st.subheader("🗺️ Bản đồ hành trình")
        alt_routes_other = [rt for i,rt in enumerate(routes) if i != selected]
        map_html = make_full_map(
            lat1, lon1, lat2, lon2,
            colored_segments=colored_segs,
            route_polyline=polyline,
            alt_routes=alt_routes_other,
            danger_markers=danger_markers,
            rest_suggestions=rest_stops,
            pois=pois,
            reports=rpts,
            forecast_segments=route_risk_forecast.get("segments") if route_risk_forecast else None,
        )
        components.html(map_html, height=620, scrolling=False)

        # ── Nút bắt đầu dẫn đường Live Navigation ────────────────────────────
        if _LIVE_NAV_OK:
            st.divider()
            _col_nav1, _col_nav2 = st.columns([3, 1])
            with _col_nav1:
                if st.button(
                    "▶️ Bắt đầu dẫn đường theo GPS",
                    type="primary",
                    use_container_width=True,
                    key="btn_start_live_nav",
                ):
                    # Truyền tuyến hiện tại sang Live Navigation
                    st.session_state["nav_active"]        = True
                    st.session_state["nav_polyline"]      = polyline
                    st.session_state["nav_risk_segs"]     = []
                    st.session_state["nav_dest"]          = (lat2, lon2)
                    st.session_state["nav_dest_name"]     = st.session_state.get("last_dest_name", f"{lat2:.4f},{lon2:.4f}")
                    st.session_state["nav_origin"]        = (lat1, lon1)
                    st.session_state["nav_mode"]          = mode
                    st.session_state["nav_progress_idx"]  = 0
                    st.session_state["nav_max_progress"]  = 0
                    st.session_state["nav_offroute"]      = False
                    st.session_state["nav_reroute_pl"]    = None
                    st.session_state["nav_reroute_risk"]  = None
                    st.session_state["nav_last_reroute"]  = 0.0
                    st.session_state["nav_gps_lat"]       = lat1
                    st.session_state["nav_gps_lon"]       = lon1
                    st.session_state["nav_arrived"]       = False
                    st.session_state["nav_steps"]         = route.get("steps", [])
                    st.session_state["nav_distance_left"] = route.get("distance_km", 0)
                    st.session_state["nav_step_text"]     = ""
                    st.session_state["_show_live_nav"]    = True
                    st.rerun()
            with _col_nav2:
                st.caption("🛣️ Dẫn đường thời gian thực với GPS thật")

        # Hiển thị Live Navigation nếu đang bật
        if _LIVE_NAV_OK and st.session_state.get("_show_live_nav"):
            st.divider()
            render_live_navigation(
                router=router,
                risk_engine=risk_engine,
                maps_api=maps_api,
            )

        # TABS
        tab_danger, tab_rest, tab_poi, tab_steps = st.tabs([
            f"🚨 Nguy hiểm ({len(danger_markers)})",
            f"☕ Điểm dừng ({len(rest_stops)})",
            f"📍 Địa điểm ({len(pois)})",
            "📋 Hướng dẫn",
        ])
        with tab_danger:
            if not danger_markers:
                st.markdown('<div class="alert-success">✅ Không phát hiện vùng nguy hiểm trọng yếu.</div>',
                            unsafe_allow_html=True)
            else:
                if len(danger_markers_raw) != len(danger_markers):
                    st.caption(f"Đã gom/lọc từ {len(danger_markers_raw)} điểm rủi ro thành {len(danger_markers)} vùng trọng yếu.")
            for seg in danger_markers:
                sc  = seg.get("score", 0)
                css = "alert-danger" if sc >= 0.7 else "alert-warning"
                km_label = seg.get("km_text") or f"km {seg.get('route_km',0):.0f}"
                avg_txt = f" · TB {seg.get('avg_score', sc):.0%}" if seg.get("cluster_count", 1) > 1 else ""
                st.markdown(
                    f'<div class="{css}"><b>{seg.get("icon","⚠️")} {seg.get("label","")}</b>'
                    f'<span style="float:right;font-size:.83rem">{"🔴" if sc>=0.7 else "🟡"} {sc:.0%}{avg_txt} · {km_label}</span>'
                    f'<br>{seg.get("desc","")}</div>', unsafe_allow_html=True)

        with tab_rest:
            if not rest_stops: st.info("Không có điểm dừng nghỉ.")
            for rs in rest_stops:
                st.markdown(
                    f'<div class="alert-success"><b>{rs.get("icon","☕")} {rs.get("name","")}</b>'
                    f'<span style="float:right;font-size:.83rem">km {rs.get("route_km",0):.0f}</span>'
                    f'<br>{rs.get("desc","")}</div>', unsafe_allow_html=True)

        with tab_poi:
            EMOJI2 = {"food":"🍜","nature":"🌿","scenic":"📸","culture":"🏛️",
                      "relaxation":"🏖️","ecotourism":"🌲","attraction":"⭐"}
            if not pois: st.info("Không tìm thấy địa điểm. Thử '🌐 Tất cả'.")
            for poi in pois:
                cat = poi.get("category","attraction")
                emoji = EMOJI2.get(cat,"📍")
                with st.expander(f"{emoji} **{poi['name']}** — km {poi.get('route_km',0):.0f} · ⭐{poi.get('rating','?')} · {poi.get('type','')}"):
                    c1,c2 = st.columns([3,1])
                    with c1:
                        st.markdown(f"**{poi.get('province','')}**")
                        st.caption("🏷️ " + ", ".join(poi.get("tags",[])))
                        story = ai_engine.generate_cultural_story(poi["name"],poi.get("province",""),poi.get("tags",[]))
                        st.markdown(f"*{story}*")
                    with c2:
                        st.metric("Vị trí", f"km {poi.get('route_km',0):.0f}")
                        st.metric("Cách tuyến", f"{poi.get('dist_from_route_km',0)} km")

        with tab_steps:
            steps = route.get("steps",[])
            if not steps: st.info("Không có hướng dẫn (tuyến fallback).")
            for i,s in enumerate(steps,1):
                st.markdown(
                    f'<div class="step-box"><b>{i}.</b> {s["instruction"]} '
                    f'<span style="color:#888;font-size:.8em">— {s["distance_km"]} km · {s["duration_min"]} phút</span></div>',
                    unsafe_allow_html=True)

    # ── CẢNH BÁO IOT THEO GPS THẬT ───────────────────────────────────────────
    if st.session_state.get("last_routes") and st.session_state.get("last_danger_markers"):
        st.divider()
        st.subheader("🚨 Cảnh báo IoT theo GPS thật")

        _iot_dangers  = st.session_state.get("last_danger_markers", [])
        _iot_total_km = st.session_state.get("last_route_km", 0) or 1
        _iot_polyline = st.session_state.get("last_polyline", [])

        # ── Chế độ: GPS thật hoặc mô phỏng thủ công ─────────────────────────
        _iot_mode = st.radio(
            "Chế độ hoạt động",
            ["📡 GPS tự động (điện thoại)", "🕹️ Mô phỏng thủ công"],
            horizontal=True,
            key="iot_mode_radio",
        )
        _use_gps = (_iot_mode == "📡 GPS tự động (điện thoại)")

        # ═══════════════════════════════════════════════════════════════════════
        # CHẾ ĐỘ 1: GPS THẬT
        # ═══════════════════════════════════════════════════════════════════════
        if _use_gps:
            st.caption(
                "📱 App sử dụng GPS điện thoại để tự động xác định vị trí và cảnh báo nguy hiểm "
                "theo tuyến đang chọn. Bấm **Bật GPS tự động** → trình duyệt sẽ hỏi quyền vị trí "
                "*(chỉ hỏi 1 lần)*, sau đó cập nhật mỗi 5 giây."
            )

            # ── Nhúng component JS lấy GPS ───────────────────────────────────
            gps_html = _build_gps_component_html(interval_ms=5000)
            components.html(gps_html, height=72, scrolling=False)

            # ── Nhận tọa độ từ query_params (Streamlit ≥1.27 dùng st.query_params) ─
            # Cách hoạt động: JS ghi vào localStorage; nút "Cập nhật GPS" đọc lại
            # và lưu vào session. Không cần st.experimental_rerun liên tục.
            gps_col1, gps_col2 = st.columns([3, 1])
            with gps_col1:
                _gps_input = st.text_input(
                    "📍 Nhập tọa độ GPS (lat,lon) — tự điền sau khi bấm Lấy GPS hoặc nhập tay",
                    value=st.session_state.get("gps_manual_input", ""),
                    placeholder="VD: 11.9404, 108.4583",
                    key="gps_coord_input",
                )
            with gps_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Cập nhật vị trí", key="gps_refresh", use_container_width=True):
                    st.session_state["gps_manual_input"] = _gps_input
                    st.rerun()

            # Thêm JS tự điền ô input khi GPS được lấy
            st.markdown("""
<script>
window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'tripsmart_gps') {
    const p = e.data.payload;
    const coord = p.lat.toFixed(6) + ', ' + p.lon.toFixed(6);
    // Tìm input Streamlit và gán giá trị
    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    for (const inp of inputs) {
      if (inp.placeholder && inp.placeholder.includes('lat,lon')) {
        inp.value = coord;
        inp.dispatchEvent(new Event('input', {bubbles:true}));
        break;
      }
    }
  }
});
</script>""", unsafe_allow_html=True)

            # Parse tọa độ GPS
            _gps_lat = _gps_lon = None
            _gps_raw = st.session_state.get("gps_manual_input", "") or _gps_input
            if _gps_raw and "," in _gps_raw:
                try:
                    _parts = _gps_raw.replace(" ", "").split(",")
                    _gps_lat, _gps_lon = float(_parts[0]), float(_parts[1])
                except Exception:
                    pass

            if _gps_lat is not None:
                # ── Tính trạng thái IoT từ GPS thật ─────────────────────────
                _iot = _calc_iot_state_from_gps(_gps_lat, _gps_lon, _iot_dangers, _iot_total_km)
                _state        = _iot["state"]
                _nd           = _iot["nearest_danger"]
                _nearest_dist = _iot["nearest_dist"]
                _next_d       = _iot["next_danger"]
                _next_dist    = _iot["next_danger_dist"]
                _cur_score    = _iot["cur_score"]

                # Tìm segment gần nhất trên polyline
                _seg_info = _find_nearest_segment(_gps_lat, _gps_lon, _iot_polyline) if _iot_polyline else {}
                _progress_ratio = _seg_info.get("progress_ratio", 0.0)

                # Map state → UI
                _STATE_MAP = {
                    "safe"   : ("#43a047","#f1f8e9","🟢 XANH — An toàn",   "🔕 TẮT","AN TOÀN",
                                "✅ Hành trình bình thường. Tiếp tục quan sát biển báo và điều kiện đường."),
                    "warning": ("#f9a825","#fffde7","🟡 VÀNG — Cảnh báo",  "🔕 TẮT","CẢNH BÁO",
                                "⚠️ Chú ý quan sát, giữ tốc độ an toàn, chuẩn bị vào vùng rủi ro."),
                    "danger" : ("#e53935","#fff5f5","🔴 ĐỎ — Nguy hiểm", "🔊 BẬT — Phát tiếng cảnh báo!","NGUY HIỂM",
                                "⛔ Giảm tốc độ ngay, tăng cự ly với xe trước, sẵn sàng dừng khẩn cấp."),
                }
                _led_color,_bg,_led_label,_buzzer,_state_text,_rec = _STATE_MAP[_state]
                _border = _led_color

                st.progress(_progress_ratio,
                            text=f"🚗 Tiến trình trên tuyến: {_progress_ratio:.0%} · GPS: {_gps_lat:.5f}, {_gps_lon:.5f}")

                st.markdown(
                    f'<div style="background:{_bg};border:2.5px solid {_border};border-radius:14px;'
                    f'padding:18px 22px;margin:12px 0">'
                    f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                    f'<div style="width:56px;height:56px;border-radius:50%;background:{_led_color};'
                    f'box-shadow:0 0 24px {_led_color};flex-shrink:0"></div>'
                    f'<div><div style="font-size:1.35rem;font-weight:700;color:{_border}">'
                    f'⚡ TRẠNG THÁI: {_state_text}</div>'
                    f'<div style="font-size:.86rem;color:#555">'
                    f'📡 GPS: {_gps_lat:.5f}, {_gps_lon:.5f}</div></div></div>'

                    f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px">'

                    f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                    f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">💡 LED MÔ PHỎNG</div>'
                    f'<div style="font-weight:700;color:{_led_color};font-size:.93rem">{_led_label}</div></div>'

                    f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                    f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">🔔 BUZZER MÔ PHỎNG</div>'
                    f'<div style="font-weight:700;font-size:.93rem">{_buzzer}</div></div>'

                    f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                    f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">📡 NGUY HIỂM GẦN NHẤT</div>'
                    f'<div style="font-weight:700;font-size:.93rem">'
                    + (f'≈ {_nearest_dist:.2f} km' if _nearest_dist < 900 else '✅ Không có') +
                    f'</div></div></div>'

                    + (
                        f'<div style="background:#fff3e0;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                        f'⚠️ <b>Vùng sắp tới:</b> {_next_d.get("icon","⚠️")} '
                        f'<b>{_next_d.get("label","")}</b> · {_next_dist:.1f} km'
                        f' · Rủi ro {_next_d.get("score",0):.0%}'
                        f'<br><span style="font-size:.82rem;color:#555">{_next_d.get("desc","")}</span></div>'
                        if _next_d and _next_dist < 900 else
                        '<div style="background:#e8f5e9;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                        '✅ <b>Không có vùng nguy hiểm nào phía trước.</b></div>'
                    )

                    + f'<div style="font-size:.92rem;padding:8px 4px"><b>🧭 Khuyến nghị:</b> {_rec}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Cập nhật tự động mỗi 10 giây khi GPS đang chạy ──────────
                st.markdown("""
<script>
setTimeout(function() {
  // Tìm nút Cập nhật vị trí và click tự động
  const btns = window.parent.document.querySelectorAll('button');
  for (const b of btns) {
    if (b.innerText && b.innerText.includes('Cập nhật vị trí')) {
      b.click(); break;
    }
  }
}, 10000);
</script>""", unsafe_allow_html=True)

            else:
                st.info("📡 Bấm **Bật GPS tự động** ở trên để lấy vị trí, "
                        "hoặc nhập tọa độ thủ công vào ô `lat,lon` rồi bấm **Cập nhật vị trí**.")

        # ═══════════════════════════════════════════════════════════════════════
        # CHẾ ĐỘ 2: MÔ PHỎNG THỦ CÔNG (giữ nguyên logic cũ)
        # ═══════════════════════════════════════════════════════════════════════
        else:
            st.caption(
                "🕹️ Mô phỏng xe di chuyển từng bước trên tuyến. "
                "Bấm **▶️ Tiếp theo** để tiến đến điểm kế tiếp."
            )
            _sim_dangers = sorted(_iot_dangers, key=lambda x: x.get("route_km", 0))
            _sim_steps   = [{"label":"🟢 Xuất phát","route_km":0.0,"score":0.0,
                             "type":"start","icon":"🚦","desc":"Bắt đầu hành trình."}]
            _sim_steps  += _sim_dangers
            _sim_steps  += [{"label":"🏁 Điểm đến","route_km":float(_iot_total_km),
                             "score":0.0,"type":"end","icon":"🏁","desc":"Đã đến điểm đến."}]

            if "iot_step" not in st.session_state:
                st.session_state["iot_step"] = 0
            _cur_idx = max(0, min(int(st.session_state.get("iot_step",0)), len(_sim_steps)-1))
            _cur_pt  = _sim_steps[_cur_idx]

            _next_danger = next((_p for _p in _sim_steps[_cur_idx+1:] if _p.get("score",0)>=0.40), None)
            _dist_to_danger = (_next_danger["route_km"] - _cur_pt.get("route_km",0)
                               if _next_danger else 999.0)
            _cur_score = float(_cur_pt.get("score",0))

            if _cur_score >= 0.60 or _dist_to_danger < 2.0:
                _led_color="#e53935";_bg="#fff5f5";_border="#e53935"
                _led_label="🔴 ĐỎ — Nguy hiểm";_buzzer="🔊 BẬT — Phát tiếng cảnh báo!"
                _state_text="NGUY HIỂM"
                _rec="⛔ Giảm tốc độ ngay, tăng cự ly với xe trước, sẵn sàng dừng khẩn cấp."
            elif _cur_score >= 0.35 or _dist_to_danger < 5.0:
                _led_color="#f9a825";_bg="#fffde7";_border="#f9a825"
                _led_label="🟡 VÀNG — Cảnh báo";_buzzer="🔕 TẮT"
                _state_text="CẢNH BÁO"
                _rec="⚠️ Chú ý quan sát, giữ tốc độ an toàn, chuẩn bị vào vùng rủi ro."
            else:
                _led_color="#43a047";_bg="#f1f8e9";_border="#43a047"
                _led_label="🟢 XANH — An toàn";_buzzer="🔕 TẮT"
                _state_text="AN TOÀN"
                _rec="✅ Hành trình bình thường. Tiếp tục quan sát biển báo và điều kiện đường."

            btn1,btn2,btn3,btn4 = st.columns(4)
            with btn1:
                if st.button("▶️ Bắt đầu / Tiếp theo", type="primary", key="iot_next", use_container_width=True):
                    if _cur_idx < len(_sim_steps)-1: st.session_state["iot_step"] = _cur_idx+1
                    st.rerun()
            with btn2:
                if st.button("⏮️ Quay lại", key="iot_prev", use_container_width=True):
                    if _cur_idx > 0: st.session_state["iot_step"] = _cur_idx-1
                    st.rerun()
            with btn3:
                if st.button("⏭️ Nhảy đến nguy hiểm", key="iot_jump", use_container_width=True):
                    _di = next((i for i,p in enumerate(_sim_steps) if p.get("score",0)>=0.60), None)
                    if _di is not None: st.session_state["iot_step"] = _di
                    st.rerun()
            with btn4:
                if st.button("🔄 Reset", key="iot_reset", use_container_width=True):
                    st.session_state["iot_step"] = 0; st.rerun()

            st.progress(_cur_idx/max(1,len(_sim_steps)-1),
                        text=f"Bước {_cur_idx+1}/{len(_sim_steps)} · km {_cur_pt.get('route_km',0):.1f}")

            st.markdown(
                f'<div style="background:{_bg};border:2.5px solid {_border};border-radius:14px;'
                f'padding:18px 22px;margin:12px 0">'
                f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                f'<div style="width:52px;height:52px;border-radius:50%;background:{_led_color};'
                f'box-shadow:0 0 18px {_led_color};flex-shrink:0"></div>'
                f'<div><div style="font-size:1.35rem;font-weight:700;color:{_border}">⚡ TRẠNG THÁI: {_state_text}</div>'
                f'<div style="font-size:.88rem;color:#555">📍 {_cur_pt.get("icon","📍")} '
                f'{_cur_pt.get("label","—")} · km {_cur_pt.get("route_km",0):.1f}</div></div></div>'

                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px">'
                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">💡 LED MÔ PHỎNG</div>'
                f'<div style="font-weight:700;color:{_led_color};font-size:.95rem">{_led_label}</div></div>'
                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">🔔 BUZZER MÔ PHỎNG</div>'
                f'<div style="font-weight:700;font-size:.95rem">{_buzzer}</div></div>'
                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">📡 NGUY HIỂM PHÍA TRƯỚC</div>'
                f'<div style="font-weight:700;font-size:.95rem">'
                + (f'≈ {_dist_to_danger:.1f} km' if _dist_to_danger < 900 else '✅ Không có') +
                f'</div></div></div>'
                + (
                    f'<div style="background:#fff3e0;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                    f'⚠️ <b>Vùng sắp tới:</b> {_next_danger.get("icon","⚠️")} '
                    f'<b>{_next_danger.get("label","")}</b> · km {_next_danger.get("route_km",0):.0f}'
                    f' · Rủi ro {_next_danger.get("score",0):.0%}'
                    f'<br><span style="font-size:.83rem;color:#555">{_next_danger.get("desc","")}</span></div>'
                    if _next_danger else
                    '<div style="background:#e8f5e9;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                    '✅ <b>Không có vùng nguy hiểm nào phía trước.</b></div>'
                )
                + f'<div style="font-size:.92rem;padding:8px 4px"><b>🧭 Khuyến nghị:</b> {_rec}</div></div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"📋 Toàn bộ {len(_sim_steps)} điểm mô phỏng", expanded=False):
                for i,pt in enumerate(_sim_steps):
                    sc = pt.get("score",0)
                    dot = "🔴" if sc>=0.60 else "🟡" if sc>=0.35 else "🟢"
                    active = "background:#e3f2fd;border-left:4px solid #1976d2;font-weight:700" if i==_cur_idx else ""
                    st.markdown(
                        f'<div class="step-box" style="{active}">'
                        f'{dot} <b>Bước {i+1}</b> · {pt.get("icon","📍")} {pt.get("label","—")} '
                        f'· km {pt.get("route_km",0):.1f}'
                        + (f' · Rủi ro {sc:.0%}' if sc>0 else '')
                        + f'</div>', unsafe_allow_html=True)

    # ── REROUTE ──────────────────────────────────────────────────────────────
    if st.session_state.get("last_routes"):
        st.divider()
        st.subheader("🔄 Tránh sự cố — Tính tuyến vòng")
        st.markdown('<div class="reroute-box">Nhập vị trí sự cố để tính tuyến vòng tránh.</div>',
                    unsafe_allow_html=True)
        rc1,rc2 = st.columns(2)
        with rc1:
            incident_loc = st.text_input("📍 Vị trí sự cố", placeholder="VD: 11.2,107.38", key="inc_loc")
        with rc2:
            avoid_r = st.slider("Bán kính tránh (km)", 1.0, 10.0, 3.0, 0.5, key="avoid_r")

        if st.button("🔄 Tính tuyến vòng", type="secondary", key="btn_reroute"):
            if not incident_loc:
                st.warning("Nhập vị trí sự cố trước.")
            else:
                with st.spinner("Đang tính..."):
                    ilat,ilon = resolve_location(incident_loc, maps_api)
                if not ilat:
                    st.error("❌ Không tìm được vị trí sự cố.")
                else:
                    origin = st.session_state["last_origin"]
                    dest   = st.session_state["last_dest"]
                    mode_r = st.session_state["last_mode"]

                    with st.spinner("🛣️ Tính tuyến vòng (OSRM)..."):
                        new_rt = router.reroute_around_incident(
                            origin, dest, ilat, ilon,
                            mode=mode_r, avoid_radius_km=avoid_r)

                    if new_rt and not new_rt.get("fallback"):
                        st.success(
                            f"✅ Tuyến vòng: 📏 {new_rt.get('distance_text','?')} "
                            f"· ⏱️ {new_rt.get('duration_text','?')}")

                        with st.spinner("🎨 Tô màu rủi ro tuyến mới..."):
                            new_colored  = risk_engine.score_polyline_segments(new_rt.get("polyline",[]))
                            new_analysis = risk_engine.analyze_route(new_rt.get("polyline",[]))
                            new_pois     = poi_engine.get_pois_on_route(new_rt.get("polyline",[]), style="all")

                        lat1r,lon1r = origin
                        lat2r,lon2r = dest
                        st.markdown("""
                        <div class="legend-grad">
                          <span>🔵 An toàn</span><div class="grad-bar"></div><span>🔴 Nguy hiểm</span>
                          &nbsp;|&nbsp; ⚫ Sự cố &nbsp;|&nbsp; 🟢 Điểm nghỉ
                        </div>""", unsafe_allow_html=True)
                        reroute_html = make_full_map(
                            lat1r, lon1r, lat2r, lon2r,
                            colored_segments=new_colored,
                            route_polyline=new_rt.get("polyline", []),
                            alt_routes=st.session_state["last_routes"],
                            danger_markers=_cluster_danger_markers(new_analysis.get("danger_segments",[]), max_items=8),
                            rest_suggestions=new_analysis.get("rest_suggestions",[]),
                            pois=new_pois,
                            incident_marker={"lat":ilat,"lon":ilon,
                                             "desc":f"Sự cố · bán kính tránh {avoid_r} km"},
                        )
                        components.html(reroute_html, height=540, scrolling=False)

                        steps_r = new_rt.get("steps",[])
                        if steps_r:
                            with st.expander(f"📋 Hướng dẫn tuyến vòng ({len(steps_r)} bước)"):
                                for i,s in enumerate(steps_r,1):
                                    st.markdown(
                                        f'<div class="step-box"><b>{i}.</b> {s["instruction"]} '
                                        f'<span style="color:#888;font-size:.8em">— {s["distance_km"]} km · {s["duration_min"]} phút</span></div>',
                                        unsafe_allow_html=True)
                    else:
                        st.error("❌ Không tính được tuyến vòng. OSRM không thể đến waypoint lệch.")

    # ── CẬP NHẬT ETA / DỰ BÁO RỦI RO THEO VỊ TRÍ HIỆN TẠI ───────────────────────
    if st.session_state.get("last_routes"):
        st.divider()
        st.subheader("🔄 Cập nhật ETA — Dự báo rủi ro theo vị trí hiện tại")
        st.markdown(
            '<div class="reroute-box">Nếu bạn nghỉ lâu hoặc đi nhanh/chậm hơn dự kiến, '
            'ETA ban đầu sẽ lệch. Nhập vị trí hiện tại để tính lại tuyến còn lại '
            'và dự báo rủi ro theo giờ thực tế (giờ hiện tại).</div>',
            unsafe_allow_html=True,
        )

        ec1, ec2 = st.columns([3, 1])
        with ec1:
            current_loc_input = st.text_input(
                "📍 Vị trí hiện tại của bạn",
                placeholder="VD: 11.50,108.07  hoặc  Đèo Bảo Lộc",
                key="current_loc_eta",
            )
        with ec2:
            recalc_btn = st.button("🔄 Tính lại ETA", type="primary", use_container_width=True, key="btn_recalc_eta")

        if recalc_btn:
            if not current_loc_input:
                st.warning("Nhập vị trí hiện tại trước.")
            else:
                with st.spinner("📡 Xác định vị trí hiện tại..."):
                    cur_lat, cur_lon = resolve_location(current_loc_input, maps_api)

                if not cur_lat:
                    st.error("❌ Không tìm được vị trí hiện tại. Thử dạng `lat,lon`, VD: `11.50,108.07`.")
                else:
                    dest_r = st.session_state["last_dest"]
                    mode_r = st.session_state["last_mode"]

                    with st.spinner("🛣️ Tính tuyến còn lại (OSRM)..."):
                        remaining_rt = router.get_route((cur_lat, cur_lon), dest_r, mode=mode_r)

                    if not remaining_rt or not remaining_rt.get("polyline"):
                        st.error("❌ Không tính được tuyến còn lại từ vị trí này.")
                    else:
                        now_dt = datetime.now()
                        remaining_polyline = remaining_rt.get("polyline", [])

                        with st.spinner("🤖 Dự báo lại rủi ro theo ETA mới..."):
                            ml_model_eta = init_ml_model()
                            new_forecast, new_tds, new_warn = _compute_route_forecast(
                                remaining_polyline, remaining_rt, now_dt,
                                risk_engine, ml_model_eta, weather_api,
                            )

                        eta_dest_text = (
                            (now_dt + timedelta(seconds=new_tds)).strftime('%H:%M')
                            if new_tds else '?'
                        )
                        st.success(
                            f"✅ Tuyến còn lại: 📏 {remaining_rt.get('distance_text','?')} · "
                            f"⏱️ {remaining_rt.get('duration_text','?')} · "
                            f"ETA đến đích: {eta_dest_text}"
                        )

                        # So sánh với dự báo ban đầu (nếu có)
                        if route_risk_forecast:
                            old_level = route_risk_forecast["overall_level"]
                            new_level = new_forecast["overall_level"] if new_forecast else "unknown"
                            order = {"low": 0, "medium": 1, "high": 2, "very_high": 3, "unknown": 0}
                            if order.get(new_level, 0) > order.get(old_level, 0):
                                st.markdown(
                                    '<div class="alert-danger">⚠️ Mức rủi ro tổng thể của phần tuyến còn lại '
                                    f'đã <b>tăng</b> so với dự báo ban đầu '
                                    f'({route_risk_forecast["overall_label"]} → '
                                    f'{new_forecast["overall_label"] if new_forecast else "?"}). '
                                    'Cân nhắc xem tuyến vòng ở trên.</div>',
                                    unsafe_allow_html=True,
                                )
                            elif order.get(new_level, 0) < order.get(old_level, 0):
                                st.markdown(
                                    '<div class="alert-success">✅ Mức rủi ro tổng thể của phần tuyến còn lại '
                                    f'đã <b>giảm</b> so với dự báo ban đầu '
                                    f'({route_risk_forecast["overall_label"]} → '
                                    f'{new_forecast["overall_label"] if new_forecast else "?"}).</div>',
                                    unsafe_allow_html=True,
                                )

                        if new_warn:
                            st.warning(new_warn)

                        if new_forecast:
                            _render_route_forecast(
                                new_forecast, now_dt,
                                title="Dự báo rủi ro tuyến còn lại (cập nhật theo vị trí hiện tại)",
                            )
                        else:
                            st.caption("ℹ️ AI Risk Model chưa sẵn sàng — không thể dự báo lại.")

                        with st.spinner("🎨 Vẽ bản đồ tuyến còn lại..."):
                            remaining_colored = risk_engine.score_polyline_segments(remaining_polyline)
                            remaining_analysis = risk_engine.analyze_route(remaining_polyline)

                        remaining_map_html = make_full_map(
                            cur_lat, cur_lon, dest_r[0], dest_r[1],
                            colored_segments=remaining_colored,
                            route_polyline=remaining_polyline,
                            danger_markers=_cluster_danger_markers(
                                remaining_analysis.get("danger_segments", []), max_items=8),
                            rest_suggestions=remaining_analysis.get("rest_suggestions", []),
                            forecast_segments=new_forecast.get("segments") if new_forecast else None,
                        )
                        components.html(remaining_map_html, height=520, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. KIỂM TRA RỦI RO
# ═══════════════════════════════════════════════════════════════════════════════
elif "rủi ro" in menu:
    st.title("⚠️ Kiểm tra rủi ro khu vực")
    loc_inp = st.text_input("📍 Địa điểm", placeholder="VD: Đà Lạt hoặc 11.94,108.44")
    if st.button("🔍 Phân tích", type="primary"):
        with st.spinner("Đang phân tích..."):
            lat,lon = resolve_location(loc_inp, maps_api)
        if not lat:
            st.error("❌ Không tìm được.")
        else:
            risk = risk_engine.analyze_point(lat, lon)
            wr   = weather_api.get_weather_risk(lat, lon)
            st.success(f"Tại `{lat:.4f}, {lon:.4f}`")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Tổng thể",    f"{risk_color(risk['overall_score'])} {risk['overall_score']:.0%}")
            c2.metric("🏔️ Địa chất", f"{risk_color(risk['geological'])} {risk['geological']:.0%}")
            c3.metric("🌊 Lũ lụt",   f"{risk_color(risk['flood'])} {risk['flood']:.0%}")
            c4.metric("⛰️ Sạt lở",   f"{risk_color(risk['landslide'])} {risk['landslide']:.0%}")

            sc  = risk["overall_score"]
            col = "red" if sc >= 0.7 else "orange" if sc >= 0.4 else "green"
            mm  = folium.Map([lat,lon], zoom_start=11,
                tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OSM")
            folium.CircleMarker([lat,lon], radius=25, color=col,
                fill=True, fill_opacity=0.2, weight=2).add_to(mm)
            folium.Marker([lat,lon],
                icon=folium.Icon(color=col, icon="map-marker"),
                popup=f"Rủi ro: {sc:.0%}").add_to(mm)
            components.html(mm._repr_html_(), height=380, scrolling=False)

            col_r,col_w = st.columns(2)
            with col_r:
                st.subheader("🚨 Cảnh báo địa lý")
                for a in risk.get("alerts",[]): st.markdown(f'<div class="alert-danger">{a}</div>',unsafe_allow_html=True)
                if not risk.get("alerts"): st.markdown('<div class="alert-success">✅ Khu vực an toàn</div>',unsafe_allow_html=True)
            with col_w:
                st.subheader("🌤️ Rủi ro thời tiết")
                for a in wr.get("alerts",[]): st.markdown(f'<div class="alert-warning">{a}</div>',unsafe_allow_html=True)
                if not wr.get("alerts"): st.markdown('<div class="alert-success">✅ Thời tiết ổn định</div>',unsafe_allow_html=True)
                w = wr.get("weather",{})
                if w.get("temp_c"):
                    st.caption(f"🌡️ {w['temp_c']}°C · {w.get('description','')} · 💨 {w.get('wind_speed_ms',0)} m/s")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SOS
# ═══════════════════════════════════════════════════════════════════════════════
elif "SOS" in menu:
    st.title("🆘 SOS Khẩn cấp")
    st.markdown('<div class="alert-danger">⚠️ Chỉ dùng khi thực sự có tình huống khẩn cấp!</div>',unsafe_allow_html=True)
    col_a,col_b = st.columns(2)
    with col_a:
        etype=st.selectbox("Loại khẩn cấp",["accident","medical","fire","stranded","general"],
            format_func=lambda x:{"accident":"🚗 Tai nạn","medical":"🏥 Cấp cứu",
                                   "fire":"🔥 Cháy","stranded":"🏔️ Mắc kẹt","general":"🚨 Khác"}[x])
        loc_sos=st.text_input("📍 Vị trí"); msg=st.text_area("Mô tả",height=80)
    with col_b:
        st.markdown("### 📞 Số khẩn cấp VN")
        st.table({"Dịch vụ":["🚓 Công an","🚒 Cứu hỏa","🚑 Cấp cứu","🏔️ Cứu nạn"],
                  "Số":["113","114","115","1800 599 920"]})
    if st.button("🆘 KÍCH HOẠT SOS",type="primary",use_container_width=True):
        lat,lon=resolve_location(loc_sos,maps_api) if loc_sos else (None,None)
        if not lat: lat,lon=10.7769,106.7009
        result=sos.trigger_sos(lat,lon,"user_001",etype,msg)
        st.error("🔴 SOS ĐÃ KÍCH HOẠT!")
        st.code(f"ID: {result['sos_id']}\nVị trí: {result['location_url']}")
        for c in result["contacts"]: st.markdown(f"**{c['name']}**: 📞 `{c['number']}`")
        for inst in result["instructions"]: st.markdown(f'<div class="step-box">{inst}</div>',unsafe_allow_html=True)
        st.code(result["message_template"])


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BÁO CÁO CỘNG ĐỒNG
# ═══════════════════════════════════════════════════════════════════════════════
elif "cộng đồng" in menu:
    st.title("📍 Báo cáo cộng đồng")
    tab1,tab2=st.tabs(["Xem báo cáo","Gửi báo cáo"])
    with tab1:
        loc_inp=st.text_input("📍 Vị trí trung tâm"); radius=st.slider("Bán kính (km)",5,100,30)
        if st.button("🔍 Tìm báo cáo"):
            lat,lon=resolve_location(loc_inp,maps_api)
            if lat:
                reports=crowd.get_nearby_reports(lat,lon,radius)
                st.info(f"Tìm thấy **{len(reports)}** báo cáo trong {radius} km")
                if reports:
                    mm=folium.Map([lat,lon],zoom_start=11,
                        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OSM")
                    RI={"accident":("red","exclamation-sign"),"flood":("blue","tint"),
                        "traffic_jam":("orange","road"),"bad_road":("orange","warning-sign"),
                        "landslide":("darkred","ban-circle")}
                    for r in reports:
                        c,ic=RI.get(r["type"],("gray","info-sign"))
                        folium.Marker([r["lat"],r["lon"]],
                            popup=folium.Popup(f"<b>{r['icon']} {r['label']}</b><br>{r.get('description','')}",max_width=200),
                            tooltip=f"{r['icon']} {r['label']} – {r['distance_km']} km",
                            icon=folium.Icon(color=c,icon=ic,prefix="glyphicon"),
                        ).add_to(mm)
                    components.html(mm._repr_html_(),height=420,scrolling=False)
                for r in reports[:10]:
                    st.markdown(f"**{r['icon']} {r['label']}** — {r['distance_km']} km")
                    st.caption(f"{r.get('description','')} · 👍 {r.get('upvotes',0)}")
                    if r.get("user_id") == "user_001":
                        can_delete, delete_msg = crowd.can_delete_report(r, "user_001")
                        if can_delete:
                            st.caption("🗑️ Bạn có thể tự xóa báo cáo này trong 15 phút đầu")
                            if st.button("Xóa báo cáo", key=f"del_{r['id']}"):
                                result = crowd.delete_report(r["id"], "user_001")
                                if result.get("success"):
                                    st.success("✅ Đã xóa báo cáo")
                                    st.rerun()
                                else:
                                    st.error(result.get("error", "Không thể xóa báo cáo"))
                        else:
                            st.caption(f"🔒 {delete_msg}")
    with tab2:
        r_loc=st.text_input("📍 Vị trí sự cố")
        r_type=st.selectbox("Loại sự cố",list(crowd.REPORT_TYPES.keys()),
            format_func=lambda x:f"{crowd.REPORT_TYPES[x]['icon']} {crowd.REPORT_TYPES[x]['label']}")
        r_desc=st.text_area("Mô tả",height=80); r_sev=st.slider("Mức độ",1,5,3)
        if st.button("📤 Gửi báo cáo",type="primary"):
            lat,lon=resolve_location(r_loc,maps_api)
            if lat:
                res=crowd.submit_report(lat,lon,r_type,"user_001",r_desc,r_sev)
                if res["success"]: st.success(f"✅ ID: `{res['report_id']}`")
                else: st.error(res.get("error","Lỗi"))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ĐIỂM THAM QUAN
# ═══════════════════════════════════════════════════════════════════════════════
elif "tham quan" in menu:
    st.title("🏛️ Gợi ý điểm tham quan")
    st.caption("Tìm quanh điểm cụ thể. Để xem dọc hành trình → vào **Tìm đường**.")
    loc_inp=st.text_input("📍 Vị trí")
    style=st.selectbox("Phong cách",["all","adventure","culture","food","relaxation","family"],
        format_func=lambda x:{"all":"🌐 Tất cả","adventure":"🏔️ Mạo hiểm","culture":"🏛️ Văn hoá",
            "food":"🍜 Ẩm thực","relaxation":"🏖️ Nghỉ dưỡng","family":"👨‍👩‍👧 Gia đình"}[x])
    radius=st.slider("Bán kính (km)",10,200,50)
    if st.button("🔍 Tìm",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api)
        if lat:
            pois=poi_engine.get_pois_near_point(lat,lon,style=style,radius_km=radius)
            if not pois: st.info("Không tìm thấy.")
            else:
                mm=folium.Map([lat,lon],zoom_start=9,
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OSM")
                folium.Marker([lat,lon],tooltip="Vị trí",
                    icon=folium.Icon(color="green",icon="user",prefix="glyphicon")).add_to(mm)
                for p in pois:
                    folium.Marker([p["lat"],p["lon"]],
                        popup=folium.Popup(f"<b>{p['name']}</b><br>⭐{p.get('rating','?')}",max_width=180),
                        tooltip=f"⭐ {p['name']}",
                        icon=folium.Icon(color="blue",icon="star",prefix="glyphicon"),
                    ).add_to(mm)
                components.html(mm._repr_html_(),height=400,scrolling=False)
                for p in pois:
                    with st.expander(f"📍 {p['name']} — ⭐{p.get('rating','?')} · {p.get('dist_from_route_km','?')} km"):
                        c1,c2=st.columns([2,1])
                        with c1:
                            story=ai_engine.generate_cultural_story(p["name"],p.get("province",""),p.get("tags",[]))
                            st.markdown(f"*{story}*")
                        with c2:
                            st.metric("Khoảng cách",f"{p.get('dist_from_route_km','?')} km")
                            st.metric("Rating",f"{p.get('rating','?')}/5")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. KÝ ỨC HÀNH TRÌNH
# ═══════════════════════════════════════════════════════════════════════════════
elif "Ký ức" in menu:
    from features.camera_component import get_camera_html
    import os

    EMOTION_LABELS = {1:"😞", 2:"😐", 3:"😊", 4:"😄", 5:"🤩"}

    st.title("📔 Ký ức hành trình")

    tab_new, tab_add, tab_view = st.tabs([
        "▶️ Bắt đầu hành trình",
        "📌 Thêm điểm dừng & Media",
        "📂 Xem hành trình cũ",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Tạo hành trình
    # ══════════════════════════════════════════════════════════════════════════
    with tab_new:
        st.subheader("Tạo hành trình mới")
        c1, c2 = st.columns(2)
        with c1:
            trip_title = st.text_input("Tên chuyến đi", "Hành trình của tôi")
            orig_name  = st.text_input("📍 Điểm xuất phát")
        with c2:
            dest_name = st.text_input("🏁 Điểm đến")
            st.text_area("Ghi chú ban đầu (tuỳ chọn)", height=68)

        if st.button("▶️ Bắt đầu hành trình", type="primary", use_container_width=True):
            trip = memory.start_trip("user_001", trip_title, orig_name, dest_name)
            st.session_state["current_trip_id"] = trip["trip_id"]
            st.success(f"✅ Hành trình **{trip_title}** đã bắt đầu!")
            st.info("Chuyển sang tab **📌 Thêm điểm dừng & Media** để ghi lại kỷ niệm.")

        cur_id = st.session_state.get("current_trip_id")
        if cur_id:
            cur = memory.get_trip(cur_id)
            if cur:
                st.divider()
                st.markdown(
                    f'<div class="alert-info">🚗 Đang ghi: <b>{cur["title"]}</b> '
                    f'({cur.get("origin","?")} → {cur.get("destination","?")})'
                    f'<br>ID: <code>{cur_id}</code></div>',
                    unsafe_allow_html=True)
                s = cur.get("summary", {})
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Điểm dừng", s.get("total_checkpoints", 0))
                mc2.metric("Cảm xúc TB", f"{s.get('avg_emotion',0):.1f}/5")
                mc3.metric("Ảnh/Video",  s.get("total_media", 0))
                if st.button("⏹ Kết thúc hành trình", type="secondary"):
                    st.session_state.pop("current_trip_id", None)
                    st.success("✅ Đã kết thúc và lưu hành trình.")
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — Thêm điểm dừng + camera
    # ══════════════════════════════════════════════════════════════════════════
    with tab_add:
        cur_id = st.session_state.get("current_trip_id")
        if not cur_id:
            st.warning("⚠️ Chưa có hành trình đang chạy. Vào tab **▶️ Bắt đầu** trước.")
        else:
            cur = memory.get_trip(cur_id)
            st.markdown(
                f'<div class="alert-info">📍 Hành trình: <b>{cur["title"]}</b> '
                f'— <code>{cur_id}</code></div>',
                unsafe_allow_html=True)

            # ── Thông tin điểm dừng ───────────────────────────────────────
            with st.expander("📝 Thông tin điểm dừng", expanded=True):
                fc1, fc2 = st.columns(2)
                with fc1:
                    cp_loc  = st.text_input("📍 Vị trí",
                        placeholder="VD: Đà Lạt hoặc 11.94,108.44", key="cp_loc")
                    cp_name = st.text_input("Tên địa điểm", key="cp_name")
                    cp_note = st.text_area("Ghi chú / cảm nhận", height=80, key="cp_note")
                with fc2:
                    cp_emotion = st.select_slider(
                        "Cảm xúc lúc này",
                        options=[1, 2, 3, 4, 5],
                        format_func=lambda v: {
                            1:"😞 Buồn", 2:"😐 Bình thường",
                            3:"😊 Vui",  4:"😄 Rất vui", 5:"🤩 Tuyệt vời!"}[v],
                        value=3, key="cp_emo")
                    cp_music   = st.text_input("🎵 Nhạc đang nghe", key="cp_music")
                    cp_weather = st.selectbox("🌤️ Thời tiết",
                        ["☀️ Nắng","🌤️ Có mây","🌧️ Mưa nhỏ",
                         "⛈️ Mưa to","🌫️ Sương mù","❄️ Lạnh"],
                        key="cp_weather")

            # ── Camera & Upload ───────────────────────────────────────────
            st.subheader("📷 Chụp ảnh & Quay video")

            cam_tab, upload_tab = st.tabs(["📷 Camera trực tiếp", "📁 Upload file"])

            with cam_tab:
                # Bước 1: Camera HTML
                st.markdown(
                    '<div class="alert-info" style="margin-bottom:8px">'
                    '<b>Bước 1:</b> Chụp ảnh hoặc quay video — file sẽ tự tải về máy bạn.</div>',
                    unsafe_allow_html=True)
                components.html(get_camera_html(), height=500, scrolling=False)

                # Bước 2: Upload file vừa tải về
                st.markdown(
                    '<div class="alert-success" style="margin-top:10px">'
                    '<b>Bước 2:</b> Upload file vừa tải về để lưu vào ký ức hành trình.</div>',
                    unsafe_allow_html=True)
                cam_uploads = st.file_uploader(
                    "📂 Chọn ảnh/video vừa tải về (tripsmart_photo_... hoặc tripsmart_video_...)",
                    type=["jpg","jpeg","png","webp","mp4","webm","mov"],
                    accept_multiple_files=True,
                    key="cam_uploads")

                if cam_uploads:
                    st.success(f"✅ Đã chọn {len(cam_uploads)} file")
                    prev_cols = st.columns(min(len(cam_uploads), 4))
                    for i, uf in enumerate(cam_uploads[:4]):
                        with prev_cols[i]:
                            if uf.type.startswith("image"):
                                st.image(uf, use_container_width=True)
                            else:
                                st.video(uf)
                            st.caption(uf.name)

            with upload_tab:
                st.caption("Upload ảnh hoặc video từ thư viện máy / điện thoại.")
                lib_uploads = st.file_uploader(
                    "📁 Chọn ảnh hoặc video",
                    type=["jpg","jpeg","png","webp","mp4","mov","webm","avi"],
                    accept_multiple_files=True,
                    key="lib_uploads")

                if lib_uploads:
                    st.success(f"✅ Đã chọn {len(lib_uploads)} file")
                    prev_cols = st.columns(min(len(lib_uploads), 4))
                    for i, uf in enumerate(lib_uploads[:4]):
                        with prev_cols[i]:
                            if uf.type.startswith("image"):
                                st.image(uf, use_container_width=True)
                            else:
                                st.video(uf)
                            st.caption(uf.name)

            # ── Nút LƯU ──────────────────────────────────────────────────
            st.divider()
            if st.button("💾 Lưu điểm dừng vào ký ức", type="primary",
                         use_container_width=True, key="btn_save_cp"):

                lat, lon = resolve_location(cp_loc, maps_api)
                if not lat:
                    st.error("❌ Không tìm được vị trí. Thử nhập dạng `lat,lon`.")
                else:
                    saved_media = []

                    # Gom tất cả file từ cả 2 uploader
                    all_files = list(st.session_state.get("cam_uploads") or []) + \
                                list(st.session_state.get("lib_uploads") or [])

                    for uf in all_files:
                        try:
                            uf.seek(0)
                            fp = memory.save_media_file(cur_id, uf)
                            saved_media.append(fp)
                        except Exception as e:
                            st.warning(f"Lỗi lưu {uf.name}: {e}")

                    cp = memory.add_checkpoint(
                        trip_id    = cur_id,
                        lat        = lat,
                        lon        = lon,
                        name       = cp_name or cp_loc,
                        emotion    = cp_emotion,
                        note       = cp_note,
                        weather    = cp_weather,
                        speed_kmh  = 0,
                        music      = cp_music,
                        media_paths= saved_media,
                    )

                    n = len(saved_media)
                    st.success(
                        f"✅ Đã lưu **{cp_name or cp_loc}** "
                        f"{EMOTION_LABELS.get(cp_emotion,'😊')}  \n"
                        + (f"📎 {n} file media đã lưu vào ký ức." if n
                           else "📝 Ghi chú đã lưu (không có media)."))
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — Xem hành trình cũ
    # ══════════════════════════════════════════════════════════════════════════
    with tab_view:
        st.subheader("Tất cả hành trình đã lưu")
        trips = memory.get_user_trips("user_001")

        if not trips:
            st.info("Chưa có hành trình nào. Tạo hành trình ở tab **▶️ Bắt đầu**!")
        else:
            for t in trips:
                s          = t.get("summary", {})
                is_current = t["trip_id"] == st.session_state.get("current_trip_id")
                badge      = " 🟢 *Đang chạy*" if is_current else ""

                with st.expander(
                    f"📅 **{t['title']}**{badge}  —  "
                    f"{t.get('origin','?')} → {t.get('destination','?')}  "
                    f"| {s.get('mood_summary','')}  "
                    f"| {s.get('total_checkpoints',0)} điểm  "
                    f"| 📎 {s.get('total_media',0)} media",
                    expanded=is_current,
                ):
                    hc1, hc2, hc3, hc4 = st.columns(4)
                    hc1.metric("Điểm dừng",  s.get("total_checkpoints", 0))
                    hc2.metric("Cảm xúc TB", f"{s.get('avg_emotion',0):.1f}/5")
                    hc3.metric("Ảnh/Video",  s.get("total_media", 0))
                    hc4.metric("Khoảnh khắc đẹp", s.get("best_emotion",""))

                    if s.get("best_moment"):
                        st.success(f"🌟 **{s['best_moment']}** — khoảnh khắc tuyệt nhất")

                    recap = ai_engine.generate_trip_recap(t)
                    if recap:
                        st.markdown(f"*{recap}*")

                    st.divider()

                    # Timeline checkpoint
                    checkpoints = t.get("checkpoints", [])
                    if not checkpoints:
                        st.info("Chưa có điểm dừng nào.")
                    else:
                        st.markdown(f"**🗺️ Hành trình ({len(checkpoints)} điểm dừng)**")
                        for i, cp in enumerate(checkpoints):
                            emo   = cp.get("emotion_label", "😊")
                            ts    = cp.get("timestamp","")[:16].replace("T"," ")
                            media = cp.get("media", [])

                            cc1, cc2 = st.columns([3, 1])
                            with cc1:
                                parts = [f"🕐 {ts}"]
                                if cp.get("weather"): parts.append(f"🌤️ {cp['weather']}")
                                if cp.get("music"):   parts.append(f"🎵 *{cp['music']}*")
                                st.markdown(
                                    f"**{i+1}. {emo} {cp.get('name','Điểm dừng')}**  \n"
                                    + " &nbsp;|&nbsp; ".join(parts))
                                if cp.get("note"):
                                    st.caption(f"💬 {cp['note']}")
                            with cc2:
                                st.caption(
                                    f"📍 {cp.get('lat',0):.4f}, {cp.get('lon',0):.4f}")
                                if media:
                                    st.caption(f"📎 {len(media)} file")

                            # Hiển thị ảnh/video
                            if media:
                                img_files = [f for f in media if any(
                                    f.lower().endswith(x)
                                    for x in [".jpg",".jpeg",".png",".webp"])]
                                vid_files = [f for f in media if any(
                                    f.lower().endswith(x)
                                    for x in [".mp4",".webm",".mov",".avi"])]

                                if img_files:
                                    cols = st.columns(min(len(img_files), 4))
                                    for j, fp in enumerate(img_files[:4]):
                                        with cols[j]:
                                            if os.path.exists(fp):
                                                st.image(fp, use_container_width=True,
                                                         caption=os.path.basename(fp))
                                            else:
                                                st.caption("⚠️ File không tồn tại")

                                for fp in vid_files[:2]:
                                    if os.path.exists(fp):
                                        st.video(fp)
                                        st.caption(f"🎬 {os.path.basename(fp)}")
                                    else:
                                        st.caption("⚠️ File không tồn tại")

                            # Dấu nối timeline
                            if i < len(checkpoints) - 1:
                                st.markdown(
                                    '<div style="border-left:2px dashed #334155;'
                                    'margin:4px 0 4px 14px;height:18px"></div>',
                                    unsafe_allow_html=True)

                    # Nút xoá
                    st.divider()
                    if not is_current:
                        col_del, _ = st.columns([1, 4])
                        with col_del:
                            if st.button("🗑️ Xoá hành trình",
                                         key=f"del_{t['trip_id']}",
                                         type="secondary"):
                                memory.delete_trip(t["trip_id"])
                                st.success("✅ Đã xoá.")
                                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# 7. SƠ TÁN THIÊN TAI
# ═══════════════════════════════════════════════════════════════════════════════
elif "thiên tai" in menu or "Sơ tán" in menu:
    st.title("🌪️ Sơ tán thiên tai")
    st.markdown('<div class="alert-danger">🚨 Tìm tuyến sơ tán đến vùng an toàn gần nhất</div>',unsafe_allow_html=True)
    loc_inp=st.text_input("📍 Vị trí hiện tại")
    mode=st.selectbox("Phương tiện",["car","motorbike","walk"],
        format_func=lambda x:{"car":"🚗 Ô tô","motorbike":"🏍️ Xe máy","walk":"🚶 Đi bộ"}[x])
    for z in disaster.get_all_safe_zones():
        st.caption(f"🏠 **{z['name']}** ({z['province']}) — {z['capacity']} người")
    if st.button("🚨 Tìm tuyến sơ tán",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api)
        if not lat: st.error("❌ Không tìm được vị trí.")
        else:
            with st.spinner("Đang tính..."):
                result=disaster.find_evacuation_route(lat,lon,mode)
            if result.get("error"): st.error(result["error"])
            else:
                zone=result["safe_zone"]; rt=result["route"]
                st.success(f"🏠 **{zone['name']}** — {zone['distance_km']} km")
                if rt:
                    c1,c2=st.columns(2)
                    c1.metric("📏 Khoảng cách",rt.get("distance_text","?"))
                    c2.metric("⏱️ Thời gian",rt.get("duration_text","?"))
                colored=risk_engine.score_polyline_segments(rt.get("polyline",[]) if rt else [])
                evac_html=make_full_map(lat,lon,zone["lat"],zone["lon"],
                    colored_segments=colored,
                    route_polyline=rt.get("polyline",[]) if rt else [],
                    danger_markers=[],rest_suggestions=[],pois=[])
                components.html(evac_html,height=450,scrolling=False)
                for w in result.get("warnings",[]): st.markdown(f'<div class="alert-danger">{w}</div>',unsafe_allow_html=True)
                for inst in result.get("instructions",[]): st.markdown(f'<div class="step-box">{inst}</div>',unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. THỜI TIẾT
# ═══════════════════════════════════════════════════════════════════════════════
elif "Thời tiết" in menu:
    st.title("🌤️ Thời tiết & Rủi ro")
    loc_inp=st.text_input("📍 Địa điểm",placeholder="VD: Đà Lạt")
    if st.button("🔍 Xem thời tiết",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api) if loc_inp else (11.9404,108.4383)
        if not lat: lat,lon=11.9404,108.4383
        with st.spinner("Đang tải..."): wr=weather_api.get_weather_risk(lat,lon)
        w=wr.get("weather",{}); rs=wr.get("risk_score",0)
        c1,c2,c3,c4=st.columns(4)
        temp=w.get("temp_c")
        feels=w.get("feels_like_c")
        humidity=w.get("humidity_pct")
        wind=w.get("wind_speed_ms")
        c1.metric("🌡️ Nhiệt độ",f"{temp}°C" if temp is not None else "N/A")
        c2.metric("🌡️ Cảm giác",f"{feels}°C" if feels is not None else "N/A")
        c3.metric("💧 Độ ẩm",f"{humidity}%" if humidity is not None else "N/A")
        c4.metric("💨 Gió",f"{wind} m/s" if wind is not None else "N/A")
        st.metric("⚠️ Rủi ro",f"{risk_color(rs)} {rs:.0%}")
        st.caption(w.get("description") or "Không lấy được dữ liệu thời tiết")
        st.caption(f"Nguồn dữ liệu: {w.get('source','unknown')}")
        for a in wr.get("alerts",[]): st.markdown(f'<div class="alert-warning">{a}</div>',unsafe_allow_html=True)
        if not wr.get("alerts"): st.markdown('<div class="alert-success">✅ Thời tiết ổn định</div>',unsafe_allow_html=True)
        forecast=weather_api.get_forecast(lat,lon,3)
        if forecast:
            st.subheader("📅 Dự báo 3 ngày")
            fc_cols=st.columns(min(len(forecast[:3]),3))
            for i,f in enumerate(forecast[:3]):
                with fc_cols[i]:
                    st.markdown(f"**{f.get('datetime','')[:10]}**")
                    st.metric("Nhiệt độ",f"{f.get('temp_c','?')}°C")
                    st.caption(f.get("description",""))

# ═══════════════════════════════════════════════════════════════════════════════
# 9. 🤖 AI RISK MODEL
# ═══════════════════════════════════════════════════════════════════════════════
elif "AI Risk Model" in menu:
    st.title("🤖 AI Risk Model — Random Forest")
    st.markdown(
        '<div class="alert-info">🧠 Mô hình Random Forest dự đoán rủi ro địa lý '
        'dựa trên dữ liệu vùng nguy hiểm Việt Nam</div>',
        unsafe_allow_html=True,
    )

    ml_model = init_ml_model()

    if ml_model is None:
        st.error("❌ Không thể load module `core.ml_risk_model`. Kiểm tra lại cài đặt.")
        st.stop()

    # ── Trạng thái model ────────────────────────────────────────────────────
    if not ml_model.is_ready:
        st.warning(f"⚠️ Model chưa sẵn sàng: {ml_model.error}")
        if st.button("🔄 Thử train lại"):
            with st.spinner("Đang train model..."):
                ml_model.retrain()
            st.rerun()
        st.stop()

    # ── Metrics model ────────────────────────────────────────────────────────
    metrics = ml_model.metrics
    if metrics:
        st.subheader("📊 Hiệu suất mô hình")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("🎯 Accuracy",    f"{metrics.get('accuracy', 0):.1%}")
        mc2.metric("📐 F1 Macro",    f"{metrics.get('f1_macro', 0):.1%}")
        mc3.metric("⚖️ F1 Weighted", f"{metrics.get('f1_weighted', 0):.1%}")
        mc4.metric("🔁 CV F1",       f"{metrics.get('cv_f1_mean', 0):.1%} ± {metrics.get('cv_f1_std', 0):.1%}")

        ms1, ms2 = st.columns(2)
        ms1.caption(f"📦 Tổng mẫu train: **{metrics.get('n_samples', '?')}**  |  "
                    f"Train: {metrics.get('n_train','?')} / Test: {metrics.get('n_test','?')}")
        ms2.caption(f"🗺️ Số vùng rủi ro: **{metrics.get('n_zones','?')}**  "
                    f"(trong đó từ CSV: {metrics.get('n_csv_zones','?')})")

        # Feature importance chart
        feat_imp = metrics.get("feature_importance", {})
        if feat_imp:
            import pandas as pd
            st.subheader("🔑 Các yếu tố ảnh hưởng nhiều nhất")
            sorted_feats = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:8]
            feat_names_vn = {
                "dist_nearest_km":   "📏 Khoảng cách vùng nguy hiểm",
                "nearest_score":     "⚠️ Điểm rủi ro gần nhất",
                "is_landslide_zone": "🪨 Vùng sạt lở",
                "is_flood_zone":     "🌊 Vùng lũ lụt",
                "is_bad_road_zone":  "🚧 Vùng đường xấu",
                "is_geological_zone":"🏔️ Vùng địa chất yếu",
                "zone_count_5km":    "🔢 Số vùng nguy hiểm (5km)",
                "max_score_10km":    "📈 Score cao nhất (10km)",
                "lat_normalized":    "🧭 Vĩ độ (chuẩn hóa)",
                "lon_normalized":    "🧭 Kinh độ (chuẩn hóa)",
                "lat":               "📍 Vĩ độ",
                "lon":               "📍 Kinh độ",
            }
            df_feat = pd.DataFrame(
                [(feat_names_vn.get(k, k), v) for k, v in sorted_feats],
                columns=["Yếu tố", "Mức độ ảnh hưởng"]
            )
            st.bar_chart(df_feat.set_index("Yếu tố"), use_container_width=True, height=280)

    st.divider()

    # ── Dự đoán điểm toạ độ ─────────────────────────────────────────────────
    st.subheader("🔍 Dự đoán rủi ro tại toạ độ")
    pred_col1, pred_col2 = st.columns(2)

    with pred_col1:
        pred_loc = st.text_input(
            "📍 Địa điểm hoặc toạ độ",
            placeholder="VD: Đà Lạt  hoặc  11.94, 108.44",
            key="ai_pred_loc",
        )

    with pred_col2:
        use_quick = st.selectbox("⚡ Chọn nhanh", [
            "— Nhập thủ công —",
            "TP.HCM (10.77, 106.69)",
            "Hà Nội (21.03, 105.83)",
            "Đà Lạt (11.94, 108.44)",
            "Sa Pa (22.33, 103.84) ⚠️ sạt lở",
            "Đồng Tháp (10.34, 105.32) ⚠️ lũ",
            "Đà Nẵng (16.07, 108.22)",
            "Huế (16.46, 107.59)",
            "Quy Nhơn (13.77, 109.22)",
        ], key="ai_quick")

    # Xử lý quick select
    _quick_coords = {
        "TP.HCM (10.77, 106.69)":              (10.77, 106.69),
        "Hà Nội (21.03, 105.83)":              (21.03, 105.83),
        "Đà Lạt (11.94, 108.44)":              (11.94, 108.44),
        "Sa Pa (22.33, 103.84) ⚠️ sạt lở":    (22.33, 103.84),
        "Đồng Tháp (10.34, 105.32) ⚠️ lũ":   (10.34, 105.32),
        "Đà Nẵng (16.07, 108.22)":             (16.07, 108.22),
        "Huế (16.46, 107.59)":                 (16.46, 107.59),
        "Quy Nhơn (13.77, 109.22)":            (13.77, 109.22),
    }

    pred_lat, pred_lon = None, None
    quick_val = st.session_state.get("ai_quick", "— Nhập thủ công —")
    if quick_val in _quick_coords:
        pred_lat, pred_lon = _quick_coords[quick_val]

    if st.button("🤖 Dự đoán rủi ro AI", type="primary", key="ai_predict_btn"):
        # Ưu tiên quick select; nếu không thì parse text
        if pred_lat is None:
            loc_txt = pred_loc.strip()
            if "," in loc_txt:
                try:
                    parts = loc_txt.split(",")
                    pred_lat, pred_lon = float(parts[0].strip()), float(parts[1].strip())
                except ValueError:
                    pass
            if pred_lat is None:
                # Geocode
                coords = resolve_location(loc_txt, maps_api)
                if coords and coords[0]:
                    pred_lat, pred_lon = coords

        if pred_lat is None:
            st.error("❌ Không xác định được toạ độ. Hãy nhập dạng `lat, lon` hoặc chọn thành phố nhanh.")
        else:
            with st.spinner("🧠 AI đang phân tích..."):
                result = ml_model.predict(pred_lat, pred_lon)

            if result.get("error"):
                st.error(f"❌ {result['error']}")
            else:
                # ── Kết quả chính ──────────────────────────────────────────
                color   = result["color"]
                emoji   = result["emoji"]
                label   = result["label"]
                conf    = result["confidence"]
                proba   = result.get("proba_pct", {})

                alert_cls = {
                    "Cao":       "alert-danger",
                    "Trung bình":"alert-warning",
                    "Thấp":      "alert-success",
                }.get(label, "alert-info")

                st.markdown(
                    f'<div class="{alert_cls}" style="font-size:1.15rem;padding:14px 18px">'
                    f'{emoji} <b>Mức rủi ro AI dự đoán: {label}</b> &nbsp;·&nbsp; '
                    f'Độ tin cậy: <b>{conf:.0%}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"📍 Toạ độ phân tích: `{pred_lat:.4f}, {pred_lon:.4f}`")

                # ── Xác suất 3 mức ─────────────────────────────────────────
                st.subheader("📊 Xác suất từng mức rủi ro")
                pc1, pc2, pc3 = st.columns(3)
                p_vals = result.get("proba", [0, 0, 0])
                pc1.metric("🟢 Thấp",       proba.get("Thấp",       "—"), delta=f"{p_vals[0]:.0%}" if p_vals else None)
                pc2.metric("🟡 Trung bình",  proba.get("Trung bình", "—"), delta=f"{p_vals[1]:.0%}" if p_vals else None)
                pc3.metric("🔴 Cao",         proba.get("Cao",        "—"), delta=f"{p_vals[2]:.0%}" if p_vals else None)

                # ── Yếu tố ảnh hưởng đến điểm này ─────────────────────────
                top_feats = result.get("top_features", [])
                if top_feats:
                    st.subheader("🔬 Yếu tố ảnh hưởng tại vị trí này")
                    feat_names_vn2 = {
                        "dist_nearest_km":   "📏 Khoảng cách vùng nguy hiểm gần nhất",
                        "nearest_score":     "⚠️ Điểm rủi ro vùng gần nhất",
                        "is_landslide_zone": "🪨 Nằm trong vùng sạt lở",
                        "is_flood_zone":     "🌊 Nằm trong vùng lũ lụt",
                        "is_bad_road_zone":  "🚧 Nằm trong vùng đường xấu",
                        "is_geological_zone":"🏔️ Nằm trong vùng địa chất yếu",
                        "zone_count_5km":    "🔢 Số vùng nguy hiểm trong 5km",
                        "max_score_10km":    "📈 Điểm rủi ro cao nhất trong 10km",
                        "lat_normalized":    "🧭 Vĩ độ (vị trí Bắc-Nam)",
                        "lon_normalized":    "🧭 Kinh độ (vị trí Đông-Tây)",
                        "lat":               "📍 Vĩ độ",
                        "lon":               "📍 Kinh độ",
                    }
                    for feat in top_feats:
                        fname   = feat_names_vn2.get(feat["name"], feat["name"])
                        imp_pct = feat["importance"] * 100
                        val     = feat["value"]
                        bar_w   = int(imp_pct * 3)  # max ~30% → max 90px
                        # Gán nhãn giá trị thân thiện
                        if feat["name"] in ("is_landslide_zone","is_flood_zone",
                                            "is_bad_road_zone","is_geological_zone"):
                            val_txt = "✅ Có" if val >= 0.5 else "❌ Không"
                        elif feat["name"] == "dist_nearest_km":
                            val_txt = f"{val:.1f} km"
                        elif feat["name"] == "zone_count_5km":
                            val_txt = f"{int(val)} vùng"
                        elif feat["name"] in ("nearest_score","max_score_10km"):
                            val_txt = f"{val:.0%}"
                        else:
                            val_txt = f"{val:.3f}"

                        st.markdown(
                            f"<div style='display:flex;align-items:center;gap:10px;"
                            f"margin:4px 0;font-size:.88rem'>"
                            f"<div style='width:230px'>{fname}</div>"
                            f"<div style='background:{color};height:10px;width:{bar_w}px;"
                            f"border-radius:5px;min-width:4px'></div>"
                            f"<div style='color:#555;min-width:80px'>{imp_pct:.1f}% ảnh hưởng</div>"
                            f"<div style='color:#334;font-weight:600'>{val_txt}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    st.divider()

    # ── Retrain ─────────────────────────────────────────────────────────────
    with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
        st.markdown("**🔄 Huấn luyện lại mô hình**")
        st.caption(
            "Nếu bạn vừa thêm dữ liệu mới vào `data/risk_points_vietnam.csv`, "
            "hãy retrain để model học thêm."
        )
        if st.button("🔁 Retrain ngay", key="ai_retrain"):
            with st.spinner("Đang huấn luyện lại mô hình Random Forest..."):
                result_rt = ml_model.retrain()
            if "error" in result_rt:
                st.error(f"❌ {result_rt['error']}")
            else:
                st.success(
                    f"✅ Retrain xong!  "
                    f"Accuracy: **{result_rt.get('accuracy',0):.1%}**  |  "
                    f"F1 macro: **{result_rt.get('f1_macro',0):.1%}**"
                )
                st.rerun()