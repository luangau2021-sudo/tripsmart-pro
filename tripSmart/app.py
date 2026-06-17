import streamlit as st
try:
    from streamlit_js_eval import get_geolocation, streamlit_js_eval
    _JSEVAL_OK = True
except ImportError:
    get_geolocation = None
    streamlit_js_eval = None
    _JSEVAL_OK = False
try:
    # Chỉ dùng nhịp 5 phút khi đang dẫn đường để Python đọc GPS/ETA,
    # không dùng refresh 1 giây nên không gây mờ/chớp màn hình.
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_OK = True
except ImportError:
    st_autorefresh = None
    _AUTOREFRESH_OK = False
import streamlit.components.v1 as components
import sys, os, folium, json

# ── Live Navigation: chỉ dùng các hàm tiện ích (snap GPS, reroute) ──────────
# KHÔNG dùng render_live_navigation() nữa — GPS được vẽ thẳng vào make_full_map()
try:
    from live_navigation import _snap_to_route, _hav, _do_reroute
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

# Ngưỡng màu rủi ro dùng thống nhất toàn app.
# Theo yêu cầu: chỉ khi score >= 90% mới hiển thị màu đỏ / chấm đỏ.
RED_RISK_THRESHOLD = 0.90
ORANGE_RISK_THRESHOLD = 0.65
YELLOW_RISK_THRESHOLD = 0.40


def _risk_score_float(s):
    try:
        return float(s or 0.0)
    except Exception:
        return 0.0


def _risk_level_icon(s):
    s = _risk_score_float(s)
    if s >= RED_RISK_THRESHOLD:
        return "🔴"
    if s >= ORANGE_RISK_THRESHOLD:
        return "🟠"
    if s >= YELLOW_RISK_THRESHOLD:
        return "🟡"
    return "🟢"


def _risk_alert_css(s):
    return "alert-danger" if _risk_score_float(s) >= RED_RISK_THRESHOLD else "alert-warning"


def risk_color(s):
    return _risk_level_icon(s)


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

    if cur_score >= RED_RISK_THRESHOLD:
        state = "danger"
    elif cur_score >= ORANGE_RISK_THRESHOLD or nearest_dist < 2.0:
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
    enableHighAccuracy: true, timeout: 10000, maximumAge: 1000
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



# ─────────────────────────────────────────────────────────────────────────────
# GPS SYNC + AUTO ETA HELPERS
# ─────────────────────────────────────────────────────────────────────────────
AUTO_ETA_INTERVAL_SEC = 5 * 60
GPS_MAX_AGE_SEC       = 5 * 60

# ── Tốc độ trung bình dùng để tính ETA / AI Risk Forecast ───────────────────
# Không dùng thời gian OSRM để tính ETA vì OSRM thường giả định tốc độ cao hơn
# thực tế khi đi đường Việt Nam. Các giá trị này áp dụng nhất quán cho:
# tuyến ban đầu, auto ETA, reroute, ETA thủ công và AI forecast theo thời gian.
AVG_SPEED_KMH_BY_MODE = {
    "car": 40.0,
    "motorbike": 40.0,
    "bike": 20.0,
    "walk": 5.0,
}


def _default_avg_speed_kmh_by_mode(mode: str) -> float:
    """Tốc độ ETA mặc định theo phương tiện."""
    return float(AVG_SPEED_KMH_BY_MODE.get(str(mode or "car"), 40.0))


def _avg_speed_kmh_by_mode(mode: str) -> float:
    """
    Tốc độ trung bình dùng riêng cho tính ETA.

    Lưu ý quan trọng cho Streamlit:
    - `eta_custom_speed_enabled` và `eta_custom_speed_kmh` là key của widget.
    - Không được ghi đè các key này sau khi widget đã được tạo trong cùng một lần rerun,
      nếu không sẽ gây StreamlitAPIException.
    - Vì vậy khi đã bấm Tìm đường, app dùng bộ key nội bộ `_route_eta_*` để
      đóng băng tốc độ ETA của tuyến đang hiển thị.
    """
    default_speed = _default_avg_speed_kmh_by_mode(mode)
    try:
        if st.session_state.get("_route_eta_speed_override_active"):
            enabled = bool(st.session_state.get("_route_eta_custom_speed_enabled", False))
            custom_speed = float(st.session_state.get("_route_eta_custom_speed_kmh") or default_speed)
        else:
            enabled = bool(st.session_state.get("eta_custom_speed_enabled", False))
            custom_speed = float(st.session_state.get("eta_custom_speed_kmh") or default_speed)
        if enabled and custom_speed > 0:
            return custom_speed
    except Exception:
        pass
    return default_speed


def _format_speed_label(mode: str) -> str:
    sp = _avg_speed_kmh_by_mode(mode)
    if float(sp).is_integer():
        return f"{int(sp)} km/h"
    return f"{sp:g} km/h"


def _format_default_speed_label(mode: str) -> str:
    sp = _default_avg_speed_kmh_by_mode(mode)
    if float(sp).is_integer():
        return f"{int(sp)} km/h"
    return f"{sp:g} km/h"


def _duration_seconds_by_distance_mode(distance_km, mode: str) -> float:
    """Tính thời gian đi dự kiến từ quãng đường và tốc độ trung bình theo mode."""
    try:
        dist = float(distance_km or 0)
        speed = _avg_speed_kmh_by_mode(mode)
        if dist <= 0 or speed <= 0:
            return 0.0
        return dist / speed * 3600.0
    except Exception:
        return 0.0


def _distance_km_from_polyline(polyline) -> float:
    """Fallback: tính độ dài polyline [lon,lat] bằng haversine nếu route thiếu distance_km."""
    try:
        if not polyline or len(polyline) < 2:
            return 0.0
        total = 0.0
        for a, b in zip(polyline[:-1], polyline[1:]):
            total += _haversine_km(a[1], a[0], b[1], b[0])
        return float(total)
    except Exception:
        return 0.0


def _get_route_distance_km(route: dict) -> float:
    """Lấy quãng đường route theo nhiều nguồn, ưu tiên distance_km từ router."""
    if not isinstance(route, dict):
        return 0.0
    for key in ("distance_km", "distance", "total_distance_km"):
        val = route.get(key)
        if isinstance(val, (int, float)) and float(val) > 0:
            # Nếu key distance có vẻ là mét thì đổi sang km.
            if key == "distance" and float(val) > 1000:
                return float(val) / 1000.0
            return float(val)
    # Parse chuỗi như "153.2 km" nếu có.
    try:
        import re
        txt = str(route.get("distance_text") or "")
        m = re.search(r"(\d+(?:[.,]\d+)?)", txt)
        if m:
            return float(m.group(1).replace(",", "."))
    except Exception:
        pass
    return _distance_km_from_polyline(route.get("polyline") or [])


def _apply_avg_speed_timing(route: dict, mode: str) -> dict:
    """
    Chuẩn hóa duration của route theo tốc độ trung bình đã chọn.
    Giữ lại thời gian OSRM gốc trong osrm_duration_* để không mất dữ liệu cũ.
    """
    if not isinstance(route, dict):
        return route

    dist_km = _get_route_distance_km(route)
    if dist_km > 0:
        route["distance_km"] = dist_km
        route.setdefault("distance_text", f"{dist_km:.1f} km")

    # Lưu OSRM duration gốc 1 lần để tham khảo/debug.
    if "osrm_duration_text" not in route and route.get("duration_text"):
        route["osrm_duration_text"] = route.get("duration_text")
    if "osrm_duration_min" not in route and isinstance(route.get("duration_min"), (int, float)):
        route["osrm_duration_min"] = route.get("duration_min")

    total_sec = _duration_seconds_by_distance_mode(dist_km, mode)
    if total_sec > 0:
        route["duration_seconds"] = total_sec
        route["duration_s"] = total_sec
        route["duration"] = total_sec
        route["duration_min"] = total_sec / 60.0
        route["duration_text"] = _format_duration_from_seconds(total_sec)
        route["avg_speed_kmh"] = _avg_speed_kmh_by_mode(mode)
        route["avg_speed_mode"] = mode
        route["avg_speed_custom"] = bool(st.session_state.get("eta_custom_speed_enabled", False))
        route["duration_source"] = "custom_avg_speed" if route["avg_speed_custom"] else "avg_speed"

        # Nếu step có distance_km thì duration từng step cũng theo cùng tốc độ.
        steps = route.get("steps") or []
        for s in steps:
            try:
                sd = float(s.get("distance_km") or 0)
                ss = _duration_seconds_by_distance_mode(sd, mode)
                if ss > 0:
                    s["duration_min"] = round(ss / 60.0, 1)
                    s["duration_text"] = _format_duration_from_seconds(ss)
            except Exception:
                pass
    return route


def _apply_avg_speed_timing_to_routes(routes, mode: str):
    """Áp dụng ETA theo tốc độ trung bình cho list route, không xoá chức năng cũ."""
    if not routes:
        return routes
    for rt in routes:
        _apply_avg_speed_timing(rt, mode)
    return routes


def _sync_nav_gps_from_browser(now_ts=None):
    """Đồng bộ GPS live từ trình duyệt về session_state để Python dùng."""
    import time as _time
    if now_ts is None:
        now_ts = _time.time()
    if not st.session_state.get("nav_active") or st.session_state.get("nav_arrived"):
        return False
    updated = False

    if _JSEVAL_OK and streamlit_js_eval is not None:
        try:
            raw = streamlit_js_eval(
                js_expressions="localStorage.getItem('tripsmart_gps')",
                key="sync_tripsmart_gps_localstorage",
            )
            if raw:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                lat = payload.get("lat")
                lon = payload.get("lon")
                ts  = payload.get("ts", 0)
                if isinstance(ts, (int, float)) and ts > 10_000_000_000:
                    ts = ts / 1000.0
                if lat is not None and lon is not None:
                    st.session_state["nav_gps_lat"] = float(lat)
                    st.session_state["nav_gps_lon"] = float(lon)
                    st.session_state["nav_gps_ts"]  = float(ts or now_ts)
                    st.session_state["nav_gps_source"] = "live_js"
                    updated = True
        except Exception as e:
            st.session_state["nav_gps_sync_error"] = str(e)

    gps_ts = st.session_state.get("nav_gps_ts", 0.0)
    gps_age = now_ts - gps_ts if gps_ts else 999999
    if (not updated or gps_age > GPS_MAX_AGE_SEC) and _JSEVAL_OK and get_geolocation is not None:
        try:
            geo = get_geolocation()
            if geo and isinstance(geo, dict) and geo.get("coords"):
                coords = geo.get("coords", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is not None and lon is not None:
                    st.session_state["nav_gps_lat"] = float(lat)
                    st.session_state["nav_gps_lon"] = float(lon)
                    st.session_state["nav_gps_ts"]  = now_ts
                    st.session_state["nav_gps_source"] = "geolocation_eval"
                    updated = True
        except Exception as e:
            st.session_state["nav_gps_sync_error"] = str(e)
    return updated


def _format_duration_from_seconds(seconds):
    try:
        seconds = int(seconds or 0)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return "?"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h and m:
        return f"{h} giờ {m} phút"
    if h:
        return f"{h} giờ"
    return f"{m} phút"


def _run_auto_eta_update(router, risk_engine, weather_api, dest_fallback, mode_fallback, now_ts=None):
    """Tính lại tuyến còn lại + ETA + AI Risk Forecast từ GPS hiện tại."""
    import time as _time
    if now_ts is None:
        now_ts = _time.time()
    ss = st.session_state
    if not ss.get("nav_active") or ss.get("nav_arrived"):
        return False

    g_lat = ss.get("nav_gps_lat")
    g_lon = ss.get("nav_gps_lon")
    g_ts  = ss.get("nav_gps_ts", 0.0)
    gps_age = now_ts - g_ts if g_ts else 999999
    if g_lat is None or g_lon is None:
        ss["auto_eta_status"] = "⚠️ Chưa có GPS hợp lệ — hãy bật GPS trên bản đồ."
        return False
    if gps_age > GPS_MAX_AGE_SEC:
        ss["auto_eta_status"] = "⚠️ GPS cũ hơn 5 phút — chờ tín hiệu GPS mới."
        return False

    dest = ss.get("nav_dest", dest_fallback)
    mode = ss.get("nav_mode", mode_fallback)
    try:
        rem_route = router.get_route((float(g_lat), float(g_lon)), dest, mode=mode)
        _apply_avg_speed_timing(rem_route, mode)
        if not rem_route or not rem_route.get("polyline"):
            ss["auto_eta_status"] = "⚠️ Không tính được tuyến còn lại từ GPS hiện tại."
            return False
        rem_poly = rem_route.get("polyline", [])
        now_dt = datetime.now()
        dist_rem = float(_get_route_distance_km(rem_route) or 0.0)
        total_sec = _duration_seconds_by_distance_mode(dist_rem, mode) or _get_route_duration_seconds(rem_route)
        arrival = (now_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"

        ss["nav_polyline"] = rem_poly
        ss["nav_steps"] = rem_route.get("steps", [])
        ss["nav_progress_idx"] = 0
        ss["nav_max_progress"] = 0
        ss["nav_offroute"] = False
        ss["nav_reroute_pl"] = None
        ss["nav_distance_left_osrm"] = dist_rem

        ss["auto_eta_last_ts"]       = now_ts
        ss["auto_eta_distance_km"]   = dist_rem
        ss["auto_eta_duration_text"] = rem_route.get("duration_text") or _format_duration_from_seconds(total_sec)
        ss["auto_eta_arrival"]       = arrival
        ss["auto_eta_updated_at"]    = now_dt.strftime("%H:%M:%S")
        ss["auto_eta_status"]        = "✅ Đã cập nhật ETA theo GPS hiện tại."

        try:
            ml_model = init_ml_model()
            if ml_model is not None and getattr(ml_model, "is_ready", False):
                forecast, _, _ = _compute_route_forecast(
                    rem_poly, rem_route, now_dt, risk_engine, ml_model, weather_api
                )
                ss["auto_eta_forecast"] = forecast
                ss["auto_eta_ai_ready"] = True
                ss["auto_eta_ai_status"] = "✅ đã cập nhật"
            else:
                ss["auto_eta_forecast"] = None
                ss["auto_eta_ai_ready"] = False
                ss["auto_eta_ai_status"] = "⚠️ chưa sẵn sàng"
        except Exception as e:
            ss["auto_eta_forecast"] = None
            ss["auto_eta_ai_ready"] = False
            ss["auto_eta_ai_status"] = f"⚠️ lỗi: {e}"
        return True
    except Exception as e:
        ss["auto_eta_status"] = f"⚠️ Lỗi cập nhật ETA tự động: {e}"
        return False


def _maybe_schedule_nav_rerun():
    if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
        if _AUTOREFRESH_OK and st_autorefresh is not None:
            st_autorefresh(interval=AUTO_ETA_INTERVAL_SEC * 1000, key="auto_eta_5min_refresh")


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


# ── Route view cache: tránh tính lại nguy hiểm/AI/POI mỗi lần đổi menu rồi quay lại ──
def _route_cache_key(polyline, route, mode, poi_style, departure_dt, selected=0):
    """
    Tạo key cache cho phần hiển thị tuyến.
    Nếu người dùng đổi tuyến, đổi tốc độ ETA, đổi giờ xuất phát hoặc đổi POI style
    thì key đổi → app sẽ tính lại. Nếu chỉ chuyển menu rồi quay lại → dùng cache.
    """
    import hashlib
    try:
        pts = polyline or []
        sample = []
        if pts:
            idxs = [0, len(pts)//4, len(pts)//2, (len(pts)*3)//4, len(pts)-1]
            for i in sorted(set(max(0, min(len(pts)-1, x)) for x in idxs)):
                sample.append([round(float(pts[i][0]), 5), round(float(pts[i][1]), 5)])
        payload = {
            "selected": int(selected or 0),
            "n": len(pts),
            "sample": sample,
            "dist": round(float(_get_route_distance_km(route or {}) or 0), 3),
            "dur": round(float(_get_route_duration_seconds(route or {}) or 0), 1),
            "mode": str(mode or ""),
            "poi_style": str(poi_style or ""),
            "speed": round(float(_avg_speed_kmh_by_mode(mode) or 0), 3),
            "departure": departure_dt.strftime("%Y-%m-%d %H:%M") if hasattr(departure_dt, "strftime") else str(departure_dt),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _clear_route_view_cache():
    """Xoá cache khi user bấm tìm tuyến mới để tránh dùng dữ liệu cũ."""
    for _k in ["route_view_cache", "route_view_cache_key"]:
        st.session_state.pop(_k, None)


def _parse_session_datetime(value, fallback):
    """Đọc datetime đã lưu trong session. Nếu lỗi thì dùng fallback."""
    if isinstance(value, datetime):
        return value
    try:
        if value:
            return datetime.fromisoformat(str(value))
    except Exception:
        pass
    return fallback


def _save_route_runtime_options(mode, poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level):
    """
    Đóng băng các tuỳ chọn tại thời điểm bấm Tìm đường.
    Nhờ vậy khi chuyển qua menu khác rồi quay lại, Streamlit có rerun thì app vẫn
    dùng đúng ngữ cảnh cũ và không kích hoạt phân tích tuyến lại vì default widget đổi.
    """
    st.session_state["last_poi_style"] = poi_style
    st.session_state["last_departure_dt_iso"] = departure_dt.isoformat() if hasattr(departure_dt, "isoformat") else str(departure_dt)
    st.session_state["last_use_human"] = bool(use_human)
    st.session_state["last_human_age"] = int(age)
    st.session_state["last_human_travel_hour"] = int(travel_hour)
    st.session_state["last_human_motion_sick"] = bool(motion_sick)
    st.session_state["last_human_has_children"] = bool(has_children)
    st.session_state["last_human_stress_level"] = int(stress_level)
    st.session_state["last_eta_custom_speed_enabled"] = bool(st.session_state.get("eta_custom_speed_enabled", False))
    st.session_state["last_eta_custom_speed_kmh"] = float(st.session_state.get("eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode))
    # Key nội bộ dùng khi tính ETA cho tuyến đã lưu; không phải key widget nên an toàn khi rerun.
    st.session_state["_route_eta_speed_override_active"] = True
    st.session_state["_route_eta_custom_speed_enabled"] = bool(st.session_state.get("last_eta_custom_speed_enabled", False))
    st.session_state["_route_eta_custom_speed_kmh"] = float(st.session_state.get("last_eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode))


def _restore_route_runtime_options(current_poi_style, current_departure_dt, current_use_human, current_age, current_travel_hour, current_motion_sick, current_has_children, current_stress_level):
    """Trả về bộ tuỳ chọn đã đóng băng cho tuyến đang hiển thị."""
    ss = st.session_state
    poi_style = ss.get("last_poi_style", current_poi_style)
    departure_dt = _parse_session_datetime(ss.get("last_departure_dt_iso"), current_departure_dt)
    use_human = bool(ss.get("last_use_human", current_use_human))
    age = int(ss.get("last_human_age", current_age))
    travel_hour = int(ss.get("last_human_travel_hour", current_travel_hour))
    motion_sick = bool(ss.get("last_human_motion_sick", current_motion_sick))
    has_children = bool(ss.get("last_human_has_children", current_has_children))
    stress_level = int(ss.get("last_human_stress_level", current_stress_level))

    # Khôi phục tốc độ ETA đã dùng khi bấm tìm đường bằng key nội bộ,
    # tuyệt đối không ghi vào key widget `eta_custom_speed_enabled` sau khi widget đã tạo.
    if "last_eta_custom_speed_enabled" in ss:
        ss["_route_eta_speed_override_active"] = True
        ss["_route_eta_custom_speed_enabled"] = bool(ss.get("last_eta_custom_speed_enabled"))
    if "last_eta_custom_speed_kmh" in ss:
        ss["_route_eta_custom_speed_kmh"] = float(ss.get("last_eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(ss.get("last_mode", "car")))

    return poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level


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
                _seg_score = _risk_score_float(seg.get("score", 0))
                _seg_icon = _risk_level_icon(_seg_score)
                st.markdown(
                    f'<div class="step-box">{_seg_icon} '
                    f'<b>km {seg["route_km"]:.0f}</b> · ETA {seg["eta_text"]} · '
                    f'{seg["label"]} ({_seg_score:.0%}){hz_txt}{wx_txt}</div>',
                    unsafe_allow_html=True,
                )

    for rec in route_risk_forecast.get("recommendations", []):
        st.markdown(f'<div class="alert-info">💡 {rec}</div>', unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# AI MOBILITY COPILOT — Safety Score + Risk Trajectory + Decision Cards
# ─────────────────────────────────────────────────────────────────────────────
def _safe_parse_dt(x):
    if isinstance(x, datetime):
        return x
    try:
        return datetime.fromisoformat(str(x))
    except Exception:
        return None


def _minutes_until_eta(seg, now_dt=None):
    """Số phút từ hiện tại đến ETA của segment AI forecast."""
    now_dt = now_dt or datetime.now()
    eta = _safe_parse_dt((seg or {}).get("eta"))
    if eta is None:
        try:
            txt = str((seg or {}).get("eta_text") or "")
            if ":" in txt:
                hh, mm = [int(v) for v in txt.split(":")[:2]]
                eta = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if eta < now_dt - timedelta(minutes=5):
                    eta += timedelta(days=1)
        except Exception:
            eta = None
    if eta is None:
        return None
    return (eta - now_dt).total_seconds() / 60.0


def _copilot_segment_score(seg):
    try:
        return float((seg or {}).get("score") or 0.0)
    except Exception:
        return 0.0


def _copilot_is_high(seg):
    # Chỉ coi là điểm đỏ/cực nguy hiểm khi >= 90%.
    # Các mức 65–89% vẫn là cảnh báo cam/vàng, chưa phải chấm đỏ.
    return _copilot_segment_score(seg) >= RED_RISK_THRESHOLD


def _build_mobility_copilot_state(forecast, route, danger_markers, rest_stops, mode, nav_active=False):
    """
    Tổng hợp dữ liệu thành trạng thái ra quyết định:
    - Safety Score 0–100, chỉ đo an toàn, không trộn Net Zero.
    - Risk trajectory đúng theo đoạn tuyến sẽ đi qua trong 0–15, 15–30, 30–60 phút tới.
    - Khuyến nghị hành động, nhưng không tự đổi tuyến.
    """
    now_dt = datetime.now()
    forecast = forecast or {}
    segments = list(forecast.get("segments") or [])
    danger_markers = list(danger_markers or [])
    rest_stops = list(rest_stops or [])
    dist_km = _get_route_distance_km(route or {})

    if segments:
        scores = [_copilot_segment_score(s) for s in segments]
        avg_score = sum(scores) / max(1, len(scores))
        max_score = max(scores) if scores else 0.0
        high_count = sum(1 for s in segments if _copilot_is_high(s))
        unknown_count = sum(1 for s in segments if str(s.get("level")) == "unknown")
    else:
        scores = []
        for d in danger_markers:
            try:
                scores.append(float(d.get("score") or 0.0))
            except Exception:
                pass
        avg_score = sum(scores) / max(1, len(scores)) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        high_count = sum(1 for d in danger_markers if float(d.get("score") or 0) >= RED_RISK_THRESHOLD)
        unknown_count = 0

    score = 100.0
    score -= avg_score * 45.0
    score -= max_score * 25.0
    score -= min(high_count, 6) * 4.0
    if dist_km >= 80 and not rest_stops:
        score -= 6.0
    if unknown_count:
        score -= min(unknown_count, 5) * 2.0
    if nav_active:
        score += 3.0
    safety_score = int(max(0, min(100, round(score))))

    if safety_score >= 80:
        safety_label, safety_icon, safety_css = "An toàn tương đối", "🟢", "alert-success"
    elif safety_score >= 60:
        safety_label, safety_icon, safety_css = "Cần chú ý", "🟡", "alert-warning"
    else:
        safety_label, safety_icon, safety_css = "Rủi ro cao", "🔴", "alert-danger"

    # Không dùng kiểu cộng dồn 0–30/0–60. Mỗi ô tương ứng với đoạn tuyến sẽ đi qua
    # trong khoảng thời gian đó: 0–15, 15–30, 30–60 phút tới.
    windows = [
        (0, 15, "15 phút tới"),
        (15, 30, "30 phút tới"),
        (30, 60, "60 phút tới"),
    ]
    trajectory = []
    for start_min, end_min, label in windows:
        segs_in = []
        for seg in segments:
            mins = _minutes_until_eta(seg, now_dt)
            if mins is not None and start_min <= mins <= end_min:
                segs_in.append(seg)
        if segs_in:
            top = max(segs_in, key=_copilot_segment_score)
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": top.get("level", "unknown"),
                "score": _copilot_segment_score(top),
                "desc": top.get("hazard_label") or top.get("label") or "Đoạn cần chú ý",
                "eta_text": top.get("eta_text", ""),
                "route_km": top.get("route_km", None),
                "segment": top,
            })
        elif segments:
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": "low",
                "score": 0.0,
                "desc": "Chưa phát hiện điểm rủi ro cao trên phần tuyến sẽ đi qua trong khung này",
                "segment": None,
            })
        else:
            level = "unknown" if not danger_markers else ("high" if max_score >= RED_RISK_THRESHOLD else "medium" if max_score >= YELLOW_RISK_THRESHOLD else "low")
            top = danger_markers[0] if danger_markers else None
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": level,
                "score": max_score,
                "desc": top.get("label", "Chưa có đủ dữ liệu AI theo ETA") if top else "Chưa có đủ dữ liệu AI theo ETA",
                "segment": top,
            })

    upcoming = []
    for seg in segments:
        mins = _minutes_until_eta(seg, now_dt)
        if mins is not None and 0 <= mins <= 30 and _copilot_is_high(seg):
            upcoming.append((mins, -_copilot_segment_score(seg), seg))
    upcoming.sort(key=lambda x: (x[0], x[1]))
    critical_seg = upcoming[0][2] if upcoming else None

    offroute = bool(st.session_state.get("nav_offroute", False))
    gps_age = None
    try:
        import time as _time
        gts = float(st.session_state.get("nav_gps_ts") or 0)
        gps_age = (_time.time() - gts) if gts else None
    except Exception:
        pass

    reasons = []
    if critical_seg:
        km_txt = f"km {critical_seg.get('route_km', 0):.0f}" if critical_seg.get("route_km") is not None else "đoạn phía trước"
        reasons.append(f"{_risk_level_icon(_copilot_segment_score(critical_seg))} {critical_seg.get('label','Rủi ro cao')} tại {km_txt}, ETA {critical_seg.get('eta_text','?')}.")
        if critical_seg.get("weather_alerts"):
            reasons.append("Thời tiết: " + "; ".join(critical_seg.get("weather_alerts", [])[:2]) + ".")
        if critical_seg.get("hazard_label"):
            reasons.append(f"Gần {critical_seg.get('hazard_label')}.")
    if offroute:
        reasons.append("GPS cho thấy bạn đang lệch khỏi tuyến hiện tại.")
    if max_score >= RED_RISK_THRESHOLD and not critical_seg:
        reasons.append("Tuyến có vùng rủi ro nền cao cần theo dõi.")
    if gps_age is not None and gps_age > GPS_MAX_AGE_SEC:
        reasons.append("GPS đã cũ hơn 5 phút nên độ tin cậy giảm.")
    if dist_km >= 80 and not rest_stops:
        reasons.append("Tuyến dài nhưng chưa có điểm nghỉ phù hợp được gợi ý.")

    if offroute:
        recommendation = "Nên tính lại tuyến từ GPS hiện tại."
        action = "reroute"
        rec_css = "alert-warning"
    elif critical_seg and _copilot_segment_score(critical_seg) >= RED_RISK_THRESHOLD:
        recommendation = "Nên đổi sang tuyến an toàn hơn hoặc nghỉ 15–30 phút rồi cập nhật lại dự báo."
        action = "reroute_or_rest"
        rec_css = "alert-danger"
    elif critical_seg:
        recommendation = "Nên giảm tốc, quan sát kỹ và cân nhắc tuyến an toàn hơn nếu thời tiết xấu."
        action = "caution"
        rec_css = "alert-warning"
    elif safety_score < 60:
        recommendation = "Nên xem xét tuyến an toàn hơn trước khi tiếp tục."
        action = "review"
        rec_css = "alert-warning"
    else:
        recommendation = "Có thể tiếp tục di chuyển, app sẽ tiếp tục theo dõi rủi ro phía trước."
        action = "continue"
        rec_css = "alert-success"

    confidence = 50
    if segments:
        confidence += 25
    if nav_active and gps_age is not None and gps_age <= GPS_MAX_AGE_SEC:
        confidence += 20
    if forecast.get("overall_level") and forecast.get("overall_level") != "unknown":
        confidence += 10
    if unknown_count:
        confidence -= min(20, unknown_count * 3)
    confidence = int(max(0, min(100, confidence)))

    return {
        "safety_score": safety_score,
        "safety_label": safety_label,
        "safety_icon": safety_icon,
        "safety_css": safety_css,
        "trajectory": trajectory,
        "critical_segment": critical_seg,
        "recommendation": recommendation,
        "action": action,
        "rec_css": rec_css,
        "reasons": reasons,
        "confidence": confidence,
        "avg_score": avg_score,
        "max_score": max_score,
        "high_count": high_count,
    }


def _render_mobility_copilot_state(copilot_state):
    """Render phần đọc hiểu của AI Mobility Copilot, không xử lý nút hành động."""
    cs = copilot_state or {}
    st.subheader("🧠 AI Mobility Copilot")
    st.markdown(
        f'<div class="{cs.get("safety_css","alert-info")}">'
        f'{cs.get("safety_icon","⚪")} <b>Safety Score:</b> '
        f'<span style="font-size:1.4rem;font-weight:800">{cs.get("safety_score",0)}/100</span> · '
        f'{cs.get("safety_label","Chưa xác định")}<br>'
        f'<b>Khuyến nghị:</b> {cs.get("recommendation","")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("🛡️ Điểm an toàn", f"{cs.get('safety_score', 0)}/100")
    m2.metric("⚠️ Đoạn rủi ro cao", cs.get("high_count", 0))
    m3.metric("📈 Độ tin cậy", f"{cs.get('confidence', 0)}%")

    st.markdown("**Risk Trajectory — đúng theo phần tuyến sẽ đi qua trong 15 / 30 / 60 phút tới**")
    for item in cs.get("trajectory", []):
        level = item.get("level", "unknown")
        score = float(item.get("score") or 0.0)
        icon = _risk_level_icon(score) if level != "unknown" else "⚪"
        eta_txt = f" · ETA {item.get('eta_text')}" if item.get("eta_text") else ""
        km_txt = f" · km {item.get('route_km'):.0f}" if isinstance(item.get("route_km"), (int, float)) else ""
        st.markdown(
            f'<div class="step-box">{icon} <b>{item.get("window")}</b> '
            f'<span style="color:#777">({item.get("range_text","")})</span>{km_txt}{eta_txt} · '
            f'{item.get("desc", "")} <span style="float:right">{score:.0%}</span></div>',
            unsafe_allow_html=True,
        )

    if cs.get("reasons"):
        with st.expander("🔎 Vì sao app đưa ra khuyến nghị này?", expanded=True):
            for r in cs.get("reasons", []):
                st.markdown(f"- {r}")
    else:
        st.caption("Chưa phát hiện nguyên nhân rủi ro nổi bật trong 30 phút tới.")


def _route_avg_risk_for_copilot(route_obj, risk_engine):
    try:
        analysis = risk_engine.analyze_route((route_obj or {}).get("polyline", []))
        return float(analysis.get("avg_score") or 0.0), analysis
    except Exception:
        return 9.0, {}


def _resolve_critical_coords(crit_seg, danger_markers, g_lat, g_lon):
    """
    FIX #2: Lấy tọa độ thực của điểm nguy hiểm cần tránh.
    Ưu tiên: lat/lon trong segment → tra cứu danger_markers gần nhất theo route_km
    → điểm đỏ gần nhất theo khoảng cách thực từ GPS.
    Trả về (lat, lon) hoặc (None, None) nếu không tìm được.
    """
    crit = crit_seg or {}
    # A) segment đã có tọa độ
    ilat = crit.get("lat") or crit.get("center_lat")
    ilon = crit.get("lon") or crit.get("center_lon")
    if ilat is not None and ilon is not None:
        return float(ilat), float(ilon)

    # B) Tìm trong danger_markers điểm đỏ gần route_km của segment
    route_km_target = crit.get("route_km")
    if route_km_target is not None and danger_markers:
        best, best_diff = None, 999.0
        for d in danger_markers:
            dlat = d.get("lat") or d.get("center_lat")
            dlon = d.get("lon") or d.get("center_lon")
            if dlat is None or dlon is None:
                continue
            rkm = d.get("route_km")
            if rkm is not None:
                diff = abs(float(rkm) - float(route_km_target))
                if diff < best_diff:
                    best_diff = diff
                    best = d
        if best and best_diff <= 15.0:
            return float(best.get("lat") or best.get("center_lat")), \
                   float(best.get("lon") or best.get("center_lon"))

    # C) Điểm đỏ (score >= 90%) gần GPS nhất phía trước
    if danger_markers and g_lat is not None and g_lon is not None:
        red_pts = [(d, _haversine_km(g_lat, g_lon,
                        float(d.get("lat") or d.get("center_lat") or g_lat),
                        float(d.get("lon") or d.get("center_lon") or g_lon)))
                   for d in danger_markers
                   if (d.get("lat") or d.get("center_lat")) and float(d.get("score", 0)) >= RED_RISK_THRESHOLD]
        if red_pts:
            red_pts.sort(key=lambda x: x[1])
            nearest = red_pts[0][0]
            return (float(nearest.get("lat") or nearest.get("center_lat")),
                    float(nearest.get("lon") or nearest.get("center_lon")))

    return None, None


def _route_passes_danger(polyline, danger_markers, threshold_score=RED_RISK_THRESHOLD, check_radius_km=1.5):
    """
    FIX #3: Kiểm tra tuyến mới có còn đi qua vùng nguy hiểm cao không.
    Trả về (passes: bool, max_score: float, count: int).
    """
    if not polyline or not danger_markers:
        return False, 0.0, 0
    red_markers = [d for d in danger_markers
                   if float(d.get("score", 0)) >= threshold_score
                   and (d.get("lat") or d.get("center_lat"))]
    if not red_markers:
        return False, 0.0, 0

    max_score = 0.0
    hit_count = 0
    # Lấy mẫu polyline (mỗi 5 điểm) để không quá chậm
    sample = polyline[::5] + ([polyline[-1]] if polyline else [])
    for d in red_markers:
        dlat = float(d.get("lat") or d.get("center_lat"))
        dlon = float(d.get("lon") or d.get("center_lon"))
        dscore = float(d.get("score", 0))
        for pt in sample:
            pt_lat, pt_lon = pt[1], pt[0]  # polyline là [lon, lat]
            if _haversine_km(pt_lat, pt_lon, dlat, dlon) <= check_radius_km:
                hit_count += 1
                max_score = max(max_score, dscore)
                break  # đủ 1 điểm trên tuyến là tính là "đi qua"
    return hit_count > 0, max_score, hit_count


def _accept_copilot_reroute(router, risk_engine, weather_api, mode_fallback, route_fallback=None):
    """
    Đổi tuyến theo lựa chọn người dùng.
    FIX #1: Lấy đúng tọa độ điểm nguy hiểm để tránh (không bỏ qua vì thiếu lat/lon).
    FIX #2: Thử nhiều bán kính tránh và nhiều điểm đỏ nếu cần.
    FIX #3: Kiểm tra tuyến mới có còn đi qua vùng đỏ không trước khi chấp nhận.
    """
    ss = st.session_state
    g_lat = ss.get("nav_gps_lat")
    g_lon = ss.get("nav_gps_lon")
    dest = ss.get("nav_dest") or ss.get("last_dest")
    mode = ss.get("nav_mode") or ss.get("last_mode") or mode_fallback
    if g_lat is None or g_lon is None or not dest:
        return False, "Chưa có GPS hiện tại hoặc điểm đến để đổi tuyến. Hãy bật GPS trên bản đồ trước."

    try:
        candidates = []
        crit = ss.get("copilot_critical_segment") or {}
        all_danger = ss.get("last_danger_markers") or []

        # ── FIX #1+#2: Xác định đúng tọa độ điểm cực nguy hiểm cần tránh ──────
        ilat, ilon = _resolve_critical_coords(crit, all_danger, g_lat, g_lon)

        # Lấy tất cả điểm đỏ (score >= 90%) để thử tránh nhiều điểm
        red_points = []
        if ilat is not None and ilon is not None:
            red_points.append((ilat, ilon, "điểm nguy hiểm chính"))
        for d in all_danger:
            dlat = d.get("lat") or d.get("center_lat")
            dlon = d.get("lon") or d.get("center_lon")
            if dlat and dlon and float(d.get("score", 0)) >= RED_RISK_THRESHOLD:
                pt = (float(dlat), float(dlon), d.get("label", "điểm đỏ"))
                if not any(_haversine_km(pt[0], pt[1], rp[0], rp[1]) < 0.5
                           for rp in red_points):
                    red_points.append(pt)

        # 1) Tuyến tránh quanh điểm nguy hiểm phía trước — thử nhiều bán kính
        if red_points and hasattr(router, "reroute_around_incident"):
            for avoid_lat, avoid_lon, avoid_label in red_points[:3]:  # tối đa 3 điểm
                for radius in [2.0, 4.0, 6.0]:
                    try:
                        avoid_rt = router.reroute_around_incident(
                            (float(g_lat), float(g_lon)), dest,
                            float(avoid_lat), float(avoid_lon),
                            mode=mode, avoid_radius_km=radius,
                        )
                        if avoid_rt and not avoid_rt.get("fallback") and avoid_rt.get("polyline"):
                            _apply_avg_speed_timing(avoid_rt, mode)
                            label = f"tuyến tránh {avoid_label} (r={radius}km)"
                            candidates.append((label, avoid_rt))
                            break  # bán kính nhỏ nhất đã tránh được → dùng luôn
                    except Exception:
                        continue

        # 2) Tuyến mới trực tiếp từ GPS hiện tại đến đích (dự phòng)
        try:
            direct_rt = router.get_route((float(g_lat), float(g_lon)), dest, mode=mode)
            if direct_rt and direct_rt.get("polyline"):
                _apply_avg_speed_timing(direct_rt, mode)
                candidates.append(("tuyến tính lại từ GPS", direct_rt))
        except Exception:
            pass

        if not candidates:
            return False, "Không tính được tuyến mới từ GPS hiện tại."

        # ── FIX #3: Lọc và đánh điểm tuyến — ưu tiên tuyến KHÔNG đi qua vùng đỏ ──
        base_dist = (
            _get_route_distance_km(route_fallback or {})
            or ss.get("nav_distance_left_osrm")
            or ss.get("auto_eta_distance_km")
            or None
        )
        orig_polyline = (route_fallback or {}).get("polyline") or ss.get("nav_polyline") or []

        scored = []
        for name, rt in candidates:
            dist = _get_route_distance_km(rt)
            avg_risk, _analysis = _route_avg_risk_for_copilot(rt, risk_engine)

            # Penalty: tuyến vẫn đi qua điểm đỏ
            passes_danger, danger_max, danger_count = _route_passes_danger(
                rt.get("polyline", []), all_danger, threshold_score=RED_RISK_THRESHOLD
            )
            danger_penalty = 0.60 if passes_danger else 0.0

            # Penalty: quá dài so với tuyến gốc (cho phép +40%)
            too_long_penalty = 0.0
            if base_dist and dist > float(base_dist) * 1.40:
                too_long_penalty = 0.30

            # Penalty: tuyến mới quá giống tuyến cũ (overlap > 85%)
            similarity_penalty = 0.0
            if orig_polyline and rt.get("polyline"):
                new_set = set((round(p[0], 3), round(p[1], 3)) for p in rt["polyline"])
                old_set = set((round(p[0], 3), round(p[1], 3)) for p in orig_polyline)
                overlap = len(new_set & old_set) / max(1, len(new_set))
                if overlap > 0.85:
                    similarity_penalty = 0.50

            total_score = avg_risk + danger_penalty + too_long_penalty + similarity_penalty
            scored.append((total_score, avg_risk, dist, name, rt,
                           passes_danger, danger_count, danger_max))

        scored.sort(key=lambda x: (x[0], x[2]))
        total_score, avg_risk, _, chosen_name, new_rt, still_danger, d_count, d_max = scored[0]

        # Nếu tuyến tốt nhất vẫn còn đi qua điểm nguy hiểm — cảnh báo rõ
        danger_warn = ""
        if still_danger:
            danger_warn = (
                f" ⚠️ Tuyến này vẫn còn đi qua {d_count} vùng nguy hiểm "
                f"(điểm cao nhất {d_max:.0%}). Hãy đặc biệt cẩn thận."
            )

        rem_poly = new_rt.get("polyline", [])
        ss["nav_polyline"] = rem_poly
        ss["nav_steps"] = new_rt.get("steps", [])
        ss["nav_progress_idx"] = 0
        ss["nav_max_progress"] = 0
        ss["nav_offroute"] = False
        ss["nav_reroute_pl"] = None
        ss["nav_distance_left_osrm"] = _get_route_distance_km(new_rt)
        ss["last_incident_reroute"] = new_rt
        ss["copilot_last_action"] = f"✅ Đã đổi sang {chosen_name} theo khuyến nghị Copilot.{danger_warn}"

        now_dt = datetime.now()
        total_sec = _get_route_duration_seconds(new_rt)
        ss["auto_eta_last_ts"] = __import__("time").time()
        ss["auto_eta_distance_km"] = _get_route_distance_km(new_rt)
        ss["auto_eta_duration_text"] = new_rt.get("duration_text") or _format_duration_from_seconds(total_sec)
        ss["auto_eta_arrival"] = (now_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"
        ss["auto_eta_updated_at"] = now_dt.strftime("%H:%M:%S")
        ss["auto_eta_status"] = "✅ Đã đổi tuyến và cập nhật ETA theo khuyến nghị Copilot."

        try:
            ml_model = init_ml_model()
            if ml_model is not None and getattr(ml_model, "is_ready", False):
                fc, _, _ = _compute_route_forecast(rem_poly, new_rt, now_dt, risk_engine, ml_model, weather_api)
                ss["auto_eta_forecast"] = fc
                ss["auto_eta_ai_ready"] = True
                ss["auto_eta_ai_status"] = "✅ đã cập nhật sau đổi tuyến"
        except Exception as e:
            ss["auto_eta_ai_status"] = f"⚠️ lỗi AI forecast sau đổi tuyến: {e}"
        return True, (
            f"Đã đổi sang {chosen_name}, cập nhật ETA/AI Risk Forecast. "
            f"Rủi ro nền ước tính: {avg_risk:.0%}.{danger_warn}"
        )
    except Exception as e:
        return False, f"Lỗi đổi tuyến: {e}"


def _accept_copilot_rest(router, risk_engine, weather_api, mode_fallback, delay_min=15):
    """Sau khi người dùng đã xác nhận nghỉ: dời giờ xuất phát lại, chạy lại AI forecast theo ETA mới."""
    ss = st.session_state
    mode = ss.get("nav_mode") or ss.get("last_mode") or mode_fallback
    poly = ss.get("nav_polyline") or ss.get("last_polyline") or []
    if not poly:
        return False, "Chưa có tuyến để cập nhật sau khi nghỉ."
    dist = ss.get("nav_distance_left_osrm") or ss.get("auto_eta_distance_km") or ss.get("last_route_km") or _distance_km_from_polyline(poly)
    route_tmp = {"polyline": poly, "distance_km": float(dist or 0), "steps": ss.get("nav_steps", [])}
    _apply_avg_speed_timing(route_tmp, mode)
    start_dt = datetime.now() + timedelta(minutes=int(delay_min))
    total_sec = _get_route_duration_seconds(route_tmp)
    ss["auto_eta_last_ts"] = __import__("time").time()
    ss["auto_eta_distance_km"] = _get_route_distance_km(route_tmp)
    ss["auto_eta_duration_text"] = route_tmp.get("duration_text")
    ss["auto_eta_arrival"] = (start_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"
    ss["auto_eta_updated_at"] = datetime.now().strftime("%H:%M:%S")
    ss["auto_eta_status"] = f"✅ Đã xác nhận nghỉ {delay_min} phút và cập nhật ETA."
    ss["copilot_last_action"] = f"⏸️ Đã xác nhận nghỉ {delay_min} phút rồi cập nhật lại dự báo."
    try:
        ml_model = init_ml_model()
        if ml_model is not None and getattr(ml_model, "is_ready", False):
            fc, _, _ = _compute_route_forecast(poly, route_tmp, start_dt, risk_engine, ml_model, weather_api)
            ss["auto_eta_forecast"] = fc
            ss["auto_eta_ai_ready"] = True
            ss["auto_eta_ai_status"] = f"✅ đã cập nhật sau nghỉ {delay_min} phút"
    except Exception as e:
        ss["auto_eta_ai_status"] = f"⚠️ lỗi AI forecast sau nghỉ: {e}"
    return True, f"Đã cập nhật dự báo sau khi nghỉ {delay_min} phút."

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



# ─────────────────────────────────────────────────────────────────────────────
# SOS FAMILY CONTACTS + ONE-TAP JOURNEY SOS HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _sos_init_state():
    """Khởi tạo bộ nhớ SOS trong session. Chuyển menu không mất; restart web/server thì mất."""
    if "sos_family_contacts" not in st.session_state:
        st.session_state["sos_family_contacts"] = []
    if "sos_pending_messages" not in st.session_state:
        st.session_state["sos_pending_messages"] = []


def _sos_normalize_phone_for_sms(phone: str) -> str:
    """Giữ số điện thoại ở định dạng đủ an toàn cho sms:."""
    raw = str(phone or "").strip()
    keep = ""
    for i, ch in enumerate(raw):
        if ch.isdigit() or (ch == "+" and i == 0):
            keep += ch
    return keep


def _sos_get_family_contacts():
    _sos_init_state()
    return list(st.session_state.get("sos_family_contacts", []))


def _sos_add_family_contact(name: str, phone: str):
    _sos_init_state()
    p = _sos_normalize_phone_for_sms(phone)
    if not p or len(p) < 8:
        return False, "Nhập số điện thoại hợp lệ trước khi thêm."
    contacts = st.session_state.get("sos_family_contacts", [])
    if any(_sos_normalize_phone_for_sms(c.get("phone")) == p for c in contacts):
        return False, "Số này đã có trong danh sách."
    contacts.append({"name": (name or "Người thân").strip(), "phone": p})
    st.session_state["sos_family_contacts"] = contacts
    return True, "Đã thêm số người thân."


def _sos_build_sms_link(phone: str, body: str) -> str:
    import urllib.parse as _urlparse
    phone = _sos_normalize_phone_for_sms(phone)
    return f"sms:{phone}?&body={_urlparse.quote(body or '')}"


def _sos_latest_gps_from_browser(key_suffix: str = "sos_gps"):
    """
    Đọc GPS mới nhất do bản đồ live ghi vào localStorage.
    Khi người dùng bấm nút trong Streamlit, rerun xảy ra → hàm này lấy tọa độ gần nhất.
    """
    # Ưu tiên localStorage của bản đồ live GPS
    if _JSEVAL_OK and streamlit_js_eval is not None:
        try:
            raw = streamlit_js_eval(
                js_expressions="localStorage.getItem('tripsmart_gps')",
                key=f"read_tripsmart_gps_for_{key_suffix}",
            )
            if raw:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                lat = payload.get("lat")
                lon = payload.get("lon")
                if lat is not None and lon is not None:
                    return {
                        "lat": float(lat),
                        "lon": float(lon),
                        "ts": payload.get("ts"),
                        "acc": payload.get("acc"),
                        "source": "live_map_localstorage",
                    }
        except Exception:
            pass
    # Fallback: GPS đã sync vào session khi Auto ETA/IOT chạy
    try:
        lat = st.session_state.get("nav_gps_lat")
        lon = st.session_state.get("nav_gps_lon")
        if lat is not None and lon is not None:
            return {"lat": float(lat), "lon": float(lon), "ts": st.session_state.get("nav_gps_ts"), "source": "session_nav_gps"}
    except Exception:
        pass
    return None


def _sos_message_template(etype_label, lat, lon, msg_text=""):
    now_txt = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    if lat is not None and lon is not None:
        loc_line = f"Vị trí: {float(lat):.6f}, {float(lon):.6f}\nBản đồ: https://maps.google.com/?q={float(lat):.6f},{float(lon):.6f}"
    else:
        loc_line = "Vị trí: chưa lấy được GPS. Hãy gọi lại ngay để xác minh vị trí."
    desc = str(msg_text or "").strip()
    desc_line = f"\nMô tả: {desc}" if desc else ""
    return (
        "SOS KHẨN CẤP - TripSmart Pro\n"
        f"Tôi đang gặp sự cố: {etype_label}\n"
        f"Thời gian: {now_txt}\n"
        f"{loc_line}"
        f"{desc_line}\n"
        "Vui lòng gọi lại hoặc hỗ trợ ngay khi có thể."
    )


def _render_sos_contacts_manager(prefix: str = "sos", require_hint: bool = False):
    """UI nhập số người thân dùng chung ở Tìm đường và SOS."""
    _sos_init_state()
    if require_hint:
        st.caption("Nhập số người thân trước khi bắt đầu hành trình để khi có sự cố chỉ cần bấm gửi SOS.")
    add_c1, add_c2, add_c3 = st.columns([1.2, 1.2, 0.75])
    with add_c1:
        new_name = st.text_input("Tên người thân", placeholder="VD: Mẹ, Ba, Anh...", key=f"{prefix}_new_contact_name")
    with add_c2:
        new_phone = st.text_input("Số điện thoại", placeholder="VD: 0987654321", key=f"{prefix}_new_contact_phone")
    with add_c3:
        st.write("")
        st.write("")
        if st.button("➕ Thêm số", use_container_width=True, key=f"{prefix}_add_contact"):
            ok, msg = _sos_add_family_contact(new_name, new_phone)
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

    contacts = _sos_get_family_contacts()
    if contacts:
        for idx, c in enumerate(list(contacts)):
            row_l, row_r = st.columns([4, 1])
            row_l.markdown(f"**{idx+1}. {c.get('name','Người thân')}** · `{c.get('phone','')}`")
            if row_r.button("🗑️ Xóa", key=f"{prefix}_delete_contact_{idx}", use_container_width=True):
                contacts.pop(idx)
                st.session_state["sos_family_contacts"] = contacts
                st.rerun()
    else:
        st.info("Chưa có số người thân. Hãy thêm ít nhất 1 số để bật SOS nhanh khi đi đường.")
    return contacts


def _render_one_tap_journey_sos_button(prefix: str = "journey_sos"):
    """
    Nút SOS nhanh trong sidebar.

    Nguyên lý đúng theo yêu cầu:
    - GPS KHÔNG đợi tới lúc bấm SOS mới lấy.
    - Khi đang dẫn đường, bản đồ live GPS luôn ghi vị trí mới nhất vào localStorage.
    - Component SOS này tự đọc localStorage mỗi 1 giây và giữ sẵn latestGps trong bộ nhớ JS.
    - Khi bấm SOS, nút chỉ dùng latestGps đã được cập nhật sẵn để mở SMS ngay.
    - Không gọi getCurrentPosition() trong lúc bấm SOS, nên không có bước chờ lấy GPS.
    """
    contacts = _sos_get_family_contacts()
    if not contacts:
        st.warning("Chưa có số người thân. Thêm số trước khi bắt đầu hành trình để dùng SOS nhanh.")
        return

    numbers = ",".join(_sos_normalize_phone_for_sms(c.get("phone")) for c in contacts)
    names = ", ".join(c.get("name", "Người thân") for c in contacts)

    # Fallback Python: dùng GPS gần nhất trong session nếu JS chưa đọc được localStorage.
    fallback_gps = _sos_latest_gps_from_browser(f"{prefix}_fallback") or {}

    import html as _html
    import json as _json
    payload = {
        "numbers": numbers,
        "names": names,
        "fallback_lat": fallback_gps.get("lat"),
        "fallback_lon": fallback_gps.get("lon"),
        "fallback_ts": fallback_gps.get("ts"),
    }
    payload_js = _json.dumps(payload, ensure_ascii=False)

    html = f"""
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{margin:0;font-family:Arial,sans-serif;background:transparent;}}
.sos-wrap{{border:2px solid #ff4b4b;background:#fff5f5;border-radius:14px;padding:12px;}}
.sos-title{{font-weight:700;color:#b71c1c;margin-bottom:8px;font-size:15px;}}
.sos-btn{{width:100%;border:0;border-radius:12px;padding:13px 16px;background:#ff4b4b;color:white;
font-size:16px;font-weight:800;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.18);}}
.sos-btn:active{{transform:scale(.99);}}
.sos-note{{font-size:12px;color:#666;margin-top:7px;line-height:1.35;}}
.gps-cache{{font-size:12px;margin:8px 0 2px 0;border-radius:10px;padding:7px 9px;background:#fff;border:1px solid #ffcdd2;color:#555;}}
.gps-ok{{border-color:#43a047;color:#1b5e20;background:#f1f8e9;}}
.gps-warn{{border-color:#f9a825;color:#e65100;background:#fffde7;}}
.gps-bad{{border-color:#e53935;color:#b71c1c;background:#ffebee;}}
</style></head>
<body>
<div class="sos-wrap">
  <div class="sos-title">🆘 SOS nhanh hành trình</div>
  <div id="gps-cache-status" class="gps-cache gps-warn">⏳ Đang chờ GPS live từ bản đồ...</div>
  <button class="sos-btn" onclick="sendJourneySOS()">🆘 Gửi SOS ngay</button>
  <div class="sos-note">
    Gửi đến: {_html.escape(names)}.<br>
    GPS được cập nhật sẵn mỗi 1 giây từ bản đồ; bấm SOS là mở SMS ngay, không chờ lấy vị trí.
  </div>
</div>
<script>
const SOS_DATA = {payload_js};
let latestGps = null;
let latestGpsTs = 0;
let cacheTimer = null;

function normalizeTs(ts) {{
  let n = Number(ts || 0);
  if (!n) return 0;
  if (n < 10000000000) n = n * 1000; // giây → mili giây
  return n;
}}

function setStatus(text, cls) {{
  const el = document.getElementById('gps-cache-status');
  if (!el) return;
  el.className = 'gps-cache ' + cls;
  el.textContent = text;
}}

function saveLatestGps(p, source) {{
  if (!p || p.lat == null || p.lon == null) return false;
  const lat = Number(p.lat), lon = Number(p.lon);
  if (!isFinite(lat) || !isFinite(lon)) return false;
  const ts = normalizeTs(p.ts) || Date.now();
  latestGps = {{lat: lat, lon: lon, acc: p.acc, ts: ts, source: source || 'cache'}};
  latestGpsTs = ts;
  return true;
}}

function readGpsFromLocalStorage() {{
  try {{
    const raw = localStorage.getItem('tripsmart_gps');
    if (!raw) return false;
    const p = JSON.parse(raw);
    return saveLatestGps(p, 'localStorage');
  }} catch(e) {{
    return false;
  }}
}}

function refreshGpsCacheStatus() {{
  readGpsFromLocalStorage();

  // Fallback từ Python session nếu chưa có GPS trong localStorage.
  if (!latestGps && SOS_DATA.fallback_lat != null && SOS_DATA.fallback_lon != null) {{
    saveLatestGps({{lat: SOS_DATA.fallback_lat, lon: SOS_DATA.fallback_lon, ts: SOS_DATA.fallback_ts}}, 'python_fallback');
  }}

  if (!latestGps) {{
    setStatus('⚠️ Chưa có GPS live. Hãy bật GPS trên bản đồ trước.', 'gps-bad');
    return;
  }}

  const ageSec = Math.max(0, Math.round((Date.now() - latestGpsTs) / 1000));
  const accText = latestGps.acc ? (' ±' + Math.round(Number(latestGps.acc)) + 'm') : '';
  if (ageSec <= 15) {{
    setStatus('✅ GPS đã sẵn sàng · ' + latestGps.lat.toFixed(5) + ', ' + latestGps.lon.toFixed(5) + accText + ' · mới ' + ageSec + 's', 'gps-ok');
  }} else if (ageSec <= 60) {{
    setStatus('🟡 GPS có sẵn nhưng đã ' + ageSec + 's · vẫn có thể gửi SOS', 'gps-warn');
  }} else {{
    setStatus('🔴 GPS đã cũ ' + ageSec + 's · nên bật/làm mới GPS trên bản đồ', 'gps-bad');
  }}
}}

// Nhận GPS từ iframe bản đồ nếu bản đồ postMessage lên parent.
window.addEventListener('message', function(e) {{
  try {{
    if (e.data && e.data.type === 'tripsmart_gps' && e.data.payload) {{
      saveLatestGps(e.data.payload, 'postMessage');
      try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(e.data.payload)); }} catch(err) {{}}
      refreshGpsCacheStatus();
    }}
  }} catch(err) {{}}
}});

function buildSmsBody() {{
  const gps = latestGps;
  const now = new Date().toLocaleString('vi-VN');
  let body = 'SOS KHẨN CẤP - TripSmart Pro\n' +
             'Tôi đang gặp sự cố trên hành trình.\n' +
             'Thời gian: ' + now + '\n';
  if (gps) {{
    const lat = gps.lat.toFixed(6), lon = gps.lon.toFixed(6);
    const ageSec = Math.max(0, Math.round((Date.now() - gps.ts) / 1000));
    body += 'Vị trí mới nhất: ' + lat + ', ' + lon + '\n' +
            'Bản đồ: https://maps.google.com/?q=' + lat + ',' + lon + '\n' +
            'GPS cập nhật cách đây: ' + ageSec + ' giây\n';
  }} else {{
    body += 'Vị trí: chưa lấy được GPS. Hãy gọi lại ngay để xác minh vị trí.\n';
  }}
  body += 'Vui lòng gọi lại hoặc hỗ trợ ngay khi có thể.';
  return body;
}}

function sendJourneySOS() {{
  // Không gọi geolocation ở đây. Chỉ dùng latestGps đã được cập nhật sẵn.
  refreshGpsCacheStatus();
  const uri = 'sms:' + SOS_DATA.numbers + '?&body=' + encodeURIComponent(buildSmsBody());
  try {{ window.top.location.href = uri; }} catch(e) {{ window.location.href = uri; }}
}}

refreshGpsCacheStatus();
if (cacheTimer) clearInterval(cacheTimer);
cacheTimer = setInterval(refreshGpsCacheStatus, 1000);
</script>
</body></html>
"""
    components.html(html, height=172, scrolling=False)




# ─────────────────────────────────────────────────────────────────────────────
# NET ZERO + SOCIAL IMPACT + SAFETY EDUCATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
CO2_G_PER_KM_BY_MODE = {
    "car": 180.0,       # ước tính trung bình cho ô tô xăng phổ thông
    "motorbike": 75.0, # ước tính trung bình cho xe máy
    "bike": 0.0,
    "walk": 0.0,
}


def _co2_factor_g_per_km(mode: str) -> float:
    return float(CO2_G_PER_KM_BY_MODE.get(str(mode or "car"), 180.0))


def _estimate_hazard_penalty_equiv_km(danger_markers) -> float:
    """
    Ước tính quãng đường tương đương bị lãng phí nhiên liệu nếu đi vào vùng ngập/sạt lở/đường xấu:
    phải chạy chậm, dừng chờ, quay đầu, hoặc giữ ga trong điều kiện xấu. Đây là mô hình minh bạch
    phục vụ giáo dục Net Zero, không phải đo khí thải tuyệt đối.
    """
    penalty = 0.0
    for seg in danger_markers or []:
        try:
            score = float(seg.get("score", 0) or 0)
        except Exception:
            score = 0.0
        typ = str(seg.get("type", "") or "").lower()
        txt = (str(seg.get("label", "") or "") + " " + str(seg.get("desc", "") or "")).lower()
        if any(k in typ + " " + txt for k in ["flood", "ngập", "lụt", "lũ"]):
            penalty += 2.8 * max(score, 0.35)
        elif any(k in typ + " " + txt for k in ["landslide", "sạt", "đèo", "bad_road", "đường xấu"]):
            penalty += 1.4 * max(score, 0.30)
        elif score >= 0.55:
            penalty += 0.8 * score
    return min(18.0, max(0.0, penalty))


def _render_env_social_impact(route, danger_markers, mode: str, reroute_route=None):
    """Hiển thị tác động Môi trường & Xã hội cho tuyến hiện tại và tuyến vòng nếu có."""
    mode_label = {"car":"ô tô", "motorbike":"xe máy", "bike":"xe đạp", "walk":"đi bộ"}.get(mode, mode)
    base_km = _get_route_distance_km(route or {})
    reroute_km = _get_route_distance_km(reroute_route or {}) if reroute_route else 0.0
    co2_gpkm = _co2_factor_g_per_km(mode)
    base_co2_kg = base_km * co2_gpkm / 1000.0
    penalty_km = _estimate_hazard_penalty_equiv_km(danger_markers)
    penalty_co2_kg = penalty_km * co2_gpkm / 1000.0

    if reroute_route and reroute_km > 0:
        reroute_co2_kg = reroute_km * co2_gpkm / 1000.0
        risky_total_kg = base_co2_kg + penalty_co2_kg
        net_saved_kg = risky_total_kg - reroute_co2_kg
        comparison_text = (
            f"So với tuyến gốc có rủi ro, tuyến vòng ước tính {'giảm' if net_saved_kg >= 0 else 'tăng'} "
            f"{abs(net_saved_kg):.2f} kg CO₂e."
        )
    else:
        reroute_co2_kg = None
        net_saved_kg = penalty_co2_kg
        comparison_text = (
            f"Nếu người dùng chủ động tránh vùng ngập/đường xấu, app ước tính có thể tránh lãng phí "
            f"khoảng {penalty_co2_kg:.2f} kg CO₂e do dừng chờ, quay đầu hoặc chạy chậm trong vùng rủi ro."
        )

    flood_count = 0
    high_count = 0
    for seg in danger_markers or []:
        txt = (str(seg.get("type", "") or "") + " " + str(seg.get("label", "") or "") + " " + str(seg.get("desc", "") or "")).lower()
        if any(k in txt for k in ["flood", "ngập", "lụt", "lũ"]):
            flood_count += 1
        try:
            if float(seg.get("score", 0) or 0) >= 0.6:
                high_count += 1
        except Exception:
            pass

    st.subheader("🌱 Tác động Môi trường & Xã hội")
    st.caption(
        "Mục này giúp gắn sản phẩm với Net Zero, an sinh xã hội và giáo dục an toàn. "
        "Các con số là ước tính minh bạch để so sánh phương án, không thay thế kiểm kê phát thải chính thức."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Phương tiện", mode_label)
    c2.metric("Hệ số CO₂e", f"{co2_gpkm:.0f} g/km")
    c3.metric("CO₂e tuyến gốc", f"{base_co2_kg:.2f} kg")
    c4.metric("Tiềm năng giảm", f"{max(0.0, net_saved_kg):.2f} kg")

    if reroute_co2_kg is not None:
        c5, c6, c7 = st.columns(3)
        c5.metric("Tuyến gốc", f"{base_km:.1f} km")
        c6.metric("Tuyến vòng", f"{reroute_km:.1f} km")
        c7.metric("CO₂e tuyến vòng", f"{reroute_co2_kg:.2f} kg")

    css = "alert-success" if net_saved_kg >= 0 else "alert-warning"
    st.markdown(f'<div class="{css}">🌍 <b>Net Zero:</b> {comparison_text}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="alert-info">🤝 <b>An sinh xã hội:</b> Tuyến hiện tại phát hiện {len(danger_markers or [])} vùng cần chú ý, '
        f'trong đó có {high_count} vùng rủi ro cao và {flood_count} vùng liên quan ngập/lũ. '
        'Cảnh báo sớm giúp học sinh, gia đình, người đi làm và lực lượng hỗ trợ địa phương ra quyết định an toàn hơn.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="alert-success">📚 <b>Giáo dục:</b> Dữ liệu rủi ro, thời tiết, ETA và quiz an toàn biến app thành công cụ học tập '
        'về giao thông, môi trường, tư duy phản biện và trách nhiệm cộng đồng.</div>',
        unsafe_allow_html=True,
    )



def _render_safety_quiz(key_prefix: str = "safety_quiz"):
    """
    Module Học luật & An toàn giao thông dạng quiz tự chọn.
    - Ngân hàng 50 câu.
    - Mỗi lượt lấy ngẫu nhiên 5 câu.
    - Làm xong có thể làm tiếp bộ khác hoặc thoát.
    - Không bắt buộc, không ảnh hưởng các chức năng dẫn đường/GPS/ETA/AI.
    """
    import random

    question_bank = [
        # ── A. An toàn giao thông (15 câu) ───────────────────────────────
        {
            "cat": "An toàn giao thông",
            "q": "Khi gặp đoạn đường ngập sâu, lựa chọn an toàn nhất là gì?",
            "opts": ["Tăng ga đi nhanh qua nước", "Dừng lại/đổi tuyến nếu không chắc độ sâu", "Đi sát xe lớn phía trước", "Tắt đèn để tránh chập điện"],
            "ans": 1,
            "why": "Không biết độ sâu hoặc dòng chảy thì không nên cố vượt. Đổi tuyến giúp giảm rủi ro chết máy, mất kiểm soát và quay đầu lãng phí nhiên liệu.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi đi qua đường đèo dốc, hành động nào an toàn nhất?",
            "opts": ["Đổ dốc bằng số cao để tiết kiệm xăng", "Giữ tốc độ phù hợp, quan sát và dùng phanh hợp lý", "Vượt xe ở khúc cua khuất", "Bám sát xe trước để đi nhanh hơn"],
            "ans": 1,
            "why": "Đường đèo cần tốc độ ổn định, quan sát xa và không vượt ở nơi khuất tầm nhìn.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Nếu trời mưa lớn làm tầm nhìn giảm, nên làm gì?",
            "opts": ["Tăng tốc để ra khỏi mưa", "Giảm tốc, bật đèn phù hợp và giữ khoảng cách", "Đi sát xe phía trước", "Dừng giữa làn đường"],
            "ans": 1,
            "why": "Mưa lớn làm giảm ma sát và tầm nhìn, vì vậy cần giảm tốc và tăng khoảng cách an toàn.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi app cảnh báo lệch tuyến, người dùng nên làm gì?",
            "opts": ["Tiếp tục đi nếu thấy đường vắng", "Dừng ở nơi an toàn và kiểm tra lại tuyến", "Tắt GPS", "Chạy nhanh hơn để quay lại tuyến"],
            "ans": 1,
            "why": "Khi lệch tuyến, cần kiểm tra lại ở nơi an toàn để tránh đi vào đường xấu, đường cấm hoặc vùng nguy hiểm.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi lái xe ban đêm qua khu vực lạ, lựa chọn nào hợp lý nhất?",
            "opts": ["Đi nhanh vì đường vắng", "Giảm tốc và ưu tiên tuyến rõ ràng, có cảnh báo rủi ro thấp", "Tắt định vị để tiết kiệm pin", "Chỉ nhìn biển quảng cáo ven đường"],
            "ans": 1,
            "why": "Ban đêm tầm nhìn hạn chế, nên ưu tiên tuyến an toàn và theo dõi cảnh báo rủi ro.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi thấy biển báo công trường hoặc đường hư hỏng phía trước, nên làm gì?",
            "opts": ["Giữ nguyên tốc độ", "Giảm tốc và quan sát", "Lấn làn để tránh ổ gà", "Bấm còi liên tục"],
            "ans": 1,
            "why": "Đường hư hỏng có thể gây mất lái, đặc biệt với xe máy và xe đạp.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi đang mệt hoặc buồn ngủ trên hành trình dài, nên làm gì?",
            "opts": ["Cố chạy thêm cho nhanh đến", "Tìm điểm dừng nghỉ an toàn", "Mở nhạc thật to rồi tiếp tục", "Chạy sát xe trước để tỉnh táo"],
            "ans": 1,
            "why": "Mệt mỏi làm giảm phản xạ. Điểm dừng nghỉ dọc tuyến giúp giảm nguy cơ tai nạn.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi đi xe máy qua đoạn đường trơn, cách xử lý nào tốt nhất?",
            "opts": ["Phanh gấp", "Giảm tốc từ từ, giữ tay lái ổn định", "Tăng ga nhanh", "Đánh lái mạnh để tránh trượt"],
            "ans": 1,
            "why": "Đường trơn cần thao tác nhẹ, tránh phanh gấp hoặc đánh lái đột ngột.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Vì sao không nên vừa lái xe vừa thao tác nhiều trên điện thoại?",
            "opts": ["Vì điện thoại nhanh hết pin", "Vì mất tập trung và tăng nguy cơ tai nạn", "Vì GPS sẽ sai hoàn toàn", "Vì bản đồ tự tắt"],
            "ans": 1,
            "why": "Người lái chỉ nên thao tác khi đã dừng ở nơi an toàn.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi chở trẻ nhỏ hoặc người dễ say xe, tuyến nào nên được ưu tiên?",
            "opts": ["Tuyến ngắn nhất dù nhiều đèo gắt", "Tuyến ổn định, ít cua gấp, có điểm nghỉ phù hợp", "Tuyến vắng nhất nhưng không rõ đường", "Tuyến có nhiều điểm nguy hiểm để trải nghiệm"],
            "ans": 1,
            "why": "Human-Aware Routing nên cân nhắc sức khỏe và trải nghiệm của người đi cùng.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi gặp tai nạn trên đường, điều nào nên làm trước?",
            "opts": ["Quay video đăng mạng", "Đảm bảo an toàn bản thân, cảnh báo người sau và gọi hỗ trợ khi cần", "Dừng xe giữa đường", "Bỏ đi ngay"],
            "ans": 1,
            "why": "An toàn hiện trường và hỗ trợ khẩn cấp quan trọng hơn việc ghi hình.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi đường đông xe trong nội thành, hành động nào giúp an toàn và tiết kiệm nhiên liệu hơn?",
            "opts": ["Tăng ga rồi phanh liên tục", "Giữ tốc độ đều, không chen lấn", "Bấm còi liên tục", "Đi ngược chiều nếu thấy nhanh hơn"],
            "ans": 1,
            "why": "Tốc độ đều giúp giảm hao nhiên liệu và giảm xung đột giao thông.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi app gợi ý điểm nghỉ, người dùng nên hiểu thế nào?",
            "opts": ["Bắt buộc phải dừng", "Là gợi ý để cân nhắc khi mệt, đi xa hoặc có trẻ nhỏ", "Không có giá trị", "Chỉ dành cho ô tô"],
            "ans": 1,
            "why": "Điểm nghỉ là hỗ trợ ra quyết định, không ép người dùng.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Nếu GPS báo vị trí không chính xác, nên làm gì?",
            "opts": ["Tin tuyệt đối và đi tiếp", "Kiểm tra tín hiệu, đứng nơi thoáng hơn hoặc nhập vị trí thủ công nếu cần", "Xóa app", "Tắt mạng vĩnh viễn"],
            "ans": 1,
            "why": "GPS có thể sai khi ở trong nhà, hẻm sâu hoặc vùng tín hiệu yếu.",
        },
        {
            "cat": "An toàn giao thông",
            "q": "Khi cần thay đổi tuyến, thời điểm nào là phù hợp nhất?",
            "opts": ["Đang chạy tốc độ cao", "Khi đã dừng/đi chậm ở nơi an toàn", "Ngay giữa khúc cua", "Khi vượt xe"],
            "ans": 1,
            "why": "Thao tác đổi tuyến cần đảm bảo không gây mất tập trung hoặc nguy hiểm.",
        },

        # ── B. Thiên tai – ngập lụt – sạt lở (10 câu) ───────────────────
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Khi app cảnh báo nguy cơ sạt lở cao, lựa chọn nào hợp lý nhất?",
            "opts": ["Vẫn đi vì đường ngắn hơn", "Giảm tốc, quan sát và cân nhắc tuyến an toàn hơn", "Chạy thật nhanh qua đoạn đó", "Tắt cảnh báo"],
            "ans": 1,
            "why": "Vùng sạt lở có thể thay đổi nhanh theo mưa và địa hình, nên ưu tiên an toàn hơn quãng đường ngắn.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Vì sao cùng một đoạn đường nhưng rủi ro có thể khác nhau theo giờ?",
            "opts": ["Vì màu bản đồ đổi", "Vì mưa, tối, lưu lượng xe và thời tiết thay đổi", "Vì tên đường thay đổi", "Vì điện thoại nóng lên"],
            "ans": 1,
            "why": "TripSmart Pro dùng ETA để đánh giá rủi ro theo thời điểm dự kiến đi qua từng đoạn.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Khi thấy nước chảy xiết qua đường, nên làm gì?",
            "opts": ["Cố đi nếu xe còn chạy", "Không vượt qua và tìm tuyến khác hoặc chờ hướng dẫn", "Đi nhanh để khỏi bị cuốn", "Đi theo người khác dù không biết độ sâu"],
            "ans": 1,
            "why": "Nước chảy xiết có thể cuốn xe và người, đặc biệt với xe máy.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Đoạn đường nào thường có nguy cơ sạt lở cao hơn?",
            "opts": ["Đường đèo dốc, taluy cao sau mưa lớn", "Đường bằng khô ráo", "Sân trường", "Bãi đỗ xe trong nhà"],
            "ans": 0,
            "why": "Địa hình dốc và mưa lớn là yếu tố làm tăng nguy cơ sạt lở.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Khi đường bị cây đổ chắn ngang, nên làm gì?",
            "opts": ["Luồn qua nếu còn khe nhỏ", "Báo cáo sự cố và tìm tuyến vòng an toàn", "Tự kéo cây nếu không có dụng cụ", "Chạy lên lề bất kể địa hình"],
            "ans": 1,
            "why": "Báo cáo cộng đồng và tuyến vòng giúp người khác tránh sự cố tương tự.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Nếu dự báo mưa lớn ở điểm sẽ đi qua sau 2 giờ, app nên ưu tiên điều gì?",
            "opts": ["Chỉ xem thời tiết hiện tại", "Dự báo theo ETA tại đoạn đường đó", "Bỏ qua vì chưa đến nơi", "Chỉ đổi màu giao diện"],
            "ans": 1,
            "why": "Dự báo theo ETA giúp đánh giá đúng rủi ro tại thời điểm người dùng thật sự đi qua.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Khi app báo vùng nguy hiểm nhưng thực tế bạn chưa thấy dấu hiệu rõ, nên hiểu thế nào?",
            "opts": ["App chắc chắn sai", "Đó là cảnh báo sớm để thận trọng hơn", "Cứ tăng tốc", "Tắt GPS"],
            "ans": 1,
            "why": "Cảnh báo sớm không thay thế quan sát thực tế, nhưng giúp người dùng chuẩn bị và ra quyết định tốt hơn.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Vì sao tuyến vòng đôi khi dài hơn nhưng vẫn đáng chọn?",
            "opts": ["Vì càng dài càng tốt", "Vì có thể tránh vùng ngập, sạt lở hoặc sự cố nguy hiểm", "Vì GPS thích vậy", "Vì làm app đẹp hơn"],
            "ans": 1,
            "why": "Tuyến an toàn có thể dài hơn nhưng giảm rủi ro tai nạn, mắc kẹt hoặc hư hỏng xe.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Khi có cảnh báo lũ quét ở vùng núi, người đi đường nên ưu tiên điều gì?",
            "opts": ["Đi nhanh qua suối", "Tránh khu vực trũng, suối, cầu yếu và theo dõi cảnh báo", "Dừng dưới chân taluy", "Đi vào ban đêm cho vắng"],
            "ans": 1,
            "why": "Lũ quét diễn biến nhanh, cần tránh điểm trũng và khu vực có dòng chảy mạnh.",
        },
        {
            "cat": "Thiên tai & rủi ro",
            "q": "Tại sao báo cáo cộng đồng cần có thời gian và vị trí?",
            "opts": ["Để trang trí", "Để biết sự cố có còn mới và nằm ở đâu", "Để tăng dung lượng file", "Để thay đổi màu nút"],
            "ans": 1,
            "why": "Sự cố giao thông thay đổi theo thời gian, nên vị trí và thời điểm giúp đánh giá độ tin cậy.",
        },

        # ── C. Net Zero – môi trường – nhiên liệu (10 câu) ───────────────
        {
            "cat": "Net Zero & môi trường",
            "q": "Vì sao tránh đường ngập/ùn tắc có thể giúp giảm phát thải?",
            "opts": ["Vì xe chạy ổn định hơn, ít hao nhiên liệu hơn", "Vì xe không cần xăng", "Vì GPS tự hấp thụ CO₂", "Vì đường ngập làm mất CO₂"],
            "ans": 0,
            "why": "Dừng chờ, quay đầu, tăng ga/phanh liên tục thường làm tăng tiêu hao nhiên liệu và phát thải.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Trong app, CO₂e được ước tính chủ yếu dựa trên yếu tố nào?",
            "opts": ["Màu của bản đồ", "Quãng đường và loại phương tiện", "Tên người dùng", "Số câu quiz"],
            "ans": 1,
            "why": "CO₂e tham khảo được tính theo hệ số phát thải của phương tiện nhân với quãng đường.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Phương tiện nào có phát thải trực tiếp thấp nhất trong các lựa chọn sau?",
            "opts": ["Ô tô xăng", "Xe máy xăng", "Xe đạp", "Xe tải"],
            "ans": 2,
            "why": "Xe đạp và đi bộ không phát thải trực tiếp trong quá trình di chuyển.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Tuyến ngắn hơn có luôn xanh hơn không?",
            "opts": ["Luôn luôn", "Không hẳn, còn phụ thuộc kẹt xe, đường xấu, ngập và tốc độ ổn định", "Không bao giờ", "Chỉ phụ thuộc màu đường"],
            "ans": 1,
            "why": "Tuyến ngắn nhưng kẹt, ngập hoặc phải quay đầu có thể tiêu hao nhiên liệu nhiều hơn.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Hành động nào phù hợp nhất với mục tiêu Net Zero khi di chuyển?",
            "opts": ["Nổ máy chờ lâu", "Chọn tuyến hợp lý, tránh dừng chờ/quay đầu không cần thiết", "Cố đi vào vùng ngập", "Phanh gấp liên tục"],
            "ans": 1,
            "why": "Tuyến hợp lý giúp tiết kiệm nhiên liệu, giảm hao mòn xe và giảm phát thải không cần thiết.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Số CO₂e trong app nên được hiểu như thế nào?",
            "opts": ["Là kiểm kê phát thải chính thức tuyệt đối", "Là ước tính tham khảo để so sánh và nâng cao nhận thức", "Là số ngẫu nhiên", "Là điểm thi"],
            "ans": 1,
            "why": "Các hệ số trong app dùng để tham khảo, không thay thế kiểm kê phát thải chuyên nghiệp.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Vì sao lái xe ổn định thường tiết kiệm nhiên liệu hơn?",
            "opts": ["Vì xe không cần động cơ", "Vì giảm tăng ga, phanh gấp và dừng chờ", "Vì GPS làm nhẹ xe", "Vì đường dài hơn"],
            "ans": 1,
            "why": "Tăng ga/phanh liên tục làm tiêu hao năng lượng nhiều hơn.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Nếu tuyến vòng dài hơn 2 km nhưng tránh được đoạn ngập có nguy cơ chết máy, nên đánh giá thế nào?",
            "opts": ["Chỉ nhìn quãng đường", "Cân nhắc cả rủi ro, nhiên liệu lãng phí nếu mắc kẹt và an toàn", "Luôn chọn tuyến ngắn", "Luôn chọn tuyến dài"],
            "ans": 1,
            "why": "Net Zero trong app gắn với quyết định thực tế: giảm lãng phí nhiên liệu và rủi ro, không chỉ giảm km tuyệt đối.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Báo cáo cộng đồng giúp môi trường theo cách nào?",
            "opts": ["Làm cây mọc nhanh hơn", "Giúp người khác tránh sự cố, kẹt xe hoặc quay đầu không cần thiết", "Tự động giảm khí thải toàn quốc", "Không có liên quan"],
            "ans": 1,
            "why": "Thông tin sự cố sớm giúp nhiều người tránh lãng phí thời gian và nhiên liệu.",
        },
        {
            "cat": "Net Zero & môi trường",
            "q": "Quiz Net Zero trong app có vai trò gì?",
            "opts": ["Thay thế hoàn toàn tính toán CO₂e", "Nâng cao nhận thức để người dùng hiểu lựa chọn di chuyển bền vững", "Chỉ để tăng số dòng code", "Bắt buộc mới được tìm đường"],
            "ans": 1,
            "why": "Quiz là phần giáo dục, còn module Net Zero chính vẫn gồm tính toán CO₂e và so sánh tác động hành trình.",
        },

        # ── D. Tư duy phản biện khi chọn tuyến (10 câu) ──────────────────
        {
            "cat": "Tư duy phản biện",
            "q": "Nếu tuyến an toàn dài hơn tuyến nhanh nhất 3 km nhưng tránh vùng ngập, nên đánh giá thế nào?",
            "opts": ["Luôn chọn tuyến ngắn nhất", "So sánh thời gian, rủi ro, nhiên liệu và mức an toàn", "Luôn chọn tuyến dài nhất", "Bỏ qua cảnh báo"],
            "ans": 1,
            "why": "Quyết định tốt cần cân bằng nhiều yếu tố, không chỉ nhìn quãng đường.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Khi AI Risk Model báo rủi ro cao, người dùng nên hiểu thế nào?",
            "opts": ["Chắc chắn sẽ có tai nạn", "Đây là cảnh báo xác suất để thận trọng và kiểm tra thêm", "App bị lỗi", "Không cần quan sát thực tế"],
            "ans": 1,
            "why": "AI hỗ trợ ra quyết định, không thay thế hoàn toàn quan sát và quy định giao thông.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Tại sao app cần hiển thị cả lý do rủi ro chứ không chỉ màu đỏ/vàng/xanh?",
            "opts": ["Để người dùng hiểu và ra quyết định có căn cứ", "Để màn hình nhiều chữ hơn", "Để che bản đồ", "Không có tác dụng"],
            "ans": 0,
            "why": "Giải thích nguyên nhân giúp người dùng rèn tư duy phản biện thay vì làm theo máy móc.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Nếu app và quan sát thực tế khác nhau, cách xử lý hợp lý là gì?",
            "opts": ["Tin app tuyệt đối", "Kết hợp cảnh báo app, quan sát thực tế và hướng dẫn địa phương", "Bỏ qua mọi cảnh báo", "Đi nhanh hơn"],
            "ans": 1,
            "why": "Ứng dụng là công cụ hỗ trợ, người dùng vẫn cần đánh giá bối cảnh thực tế.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Vì sao không nên chỉ tối ưu theo thời gian đến nơi?",
            "opts": ["Vì thời gian không quan trọng", "Vì tuyến nhanh có thể rủi ro hơn hoặc gây mệt mỏi hơn", "Vì bản đồ không cần ETA", "Vì xe nào cũng đi như nhau"],
            "ans": 1,
            "why": "TripSmart Pro hướng đến tuyến phù hợp với con người và bối cảnh, không chỉ nhanh nhất.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Nếu một báo cáo cộng đồng chưa được nhiều người xác nhận, nên làm gì?",
            "opts": ["Tin tuyệt đối", "Xem như thông tin tham khảo và kiểm tra thêm", "Xóa tuyến", "Bỏ qua vì không chắc chắn"],
            "ans": 1,
            "why": "Dữ liệu cộng đồng hữu ích nhưng cần đánh giá độ mới, vị trí và mức xác nhận.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Khi chọn tuyến cho gia đình có trẻ nhỏ, yếu tố nào nên cân nhắc thêm ngoài thời gian?",
            "opts": ["Điểm nghỉ, độ ổn định tuyến, rủi ro đường và thời tiết", "Màu nút bấm", "Tên đường dài hay ngắn", "Số icon trên bản đồ"],
            "ans": 0,
            "why": "Human-Aware Routing đặt nhu cầu con người vào quyết định chọn tuyến.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Khi thấy tuyến vòng dài hơn nhưng điểm rủi ro thấp hơn, câu hỏi nào nên đặt ra?",
            "opts": ["Tuyến nào cân bằng tốt giữa an toàn, thời gian và nhiên liệu?", "Tuyến nào có màu đẹp hơn?", "Tuyến nào có nhiều chữ hơn?", "Tuyến nào bắt buộc phải chọn?"],
            "ans": 0,
            "why": "Đây là cách đánh giá đa tiêu chí, phù hợp với tư duy phản biện.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Vì sao app nên cho phép tùy chỉnh tốc độ ETA?",
            "opts": ["Vì tốc độ thực tế khác nhau theo người, phương tiện và điều kiện đường", "Vì OSRM luôn sai", "Vì không cần tính thời gian", "Vì để làm khó người dùng"],
            "ans": 0,
            "why": "Tốc độ trung bình cố định giúp dự báo thực tế hơn khi người dùng đi chậm/nhanh khác nhau.",
        },
        {
            "cat": "Tư duy phản biện",
            "q": "Khi dữ liệu thời tiết dự báo quá xa, app nên làm gì?",
            "opts": ["Vẫn khẳng định chắc chắn", "Đánh dấu độ tin cậy thấp/không xác định", "Ẩn toàn bộ tuyến", "Tự bịa dữ liệu"],
            "ans": 1,
            "why": "Dự báo càng xa càng kém chắc chắn, nên cần minh bạch độ tin cậy.",
        },

        # ── E. Kỹ năng dùng app / SOS / cộng đồng (5 câu) ────────────────
        {
            "cat": "Kỹ năng dùng app",
            "q": "Chức năng SOS trong app nên được dùng khi nào?",
            "opts": ["Khi gặp tình huống khẩn cấp hoặc cần hỗ trợ", "Khi muốn đổi màu bản đồ", "Khi muốn chơi quiz", "Khi hết pin"],
            "ans": 0,
            "why": "SOS là công cụ hỗ trợ tình huống khẩn cấp, cần dùng đúng mục đích.",
        },
        {
            "cat": "Kỹ năng dùng app",
            "q": "Khi gửi báo cáo cộng đồng, thông tin nào quan trọng nhất?",
            "opts": ["Vị trí, loại sự cố và mô tả ngắn", "Màu áo người gửi", "Tên bài hát đang nghe", "Số lượng icon"],
            "ans": 0,
            "why": "Báo cáo cần đủ vị trí và loại sự cố để người khác hiểu và tránh rủi ro.",
        },
        {
            "cat": "Kỹ năng dùng app",
            "q": "Vì sao cần bật quyền vị trí khi dùng GPS live?",
            "opts": ["Để app biết vị trí hiện tại và cập nhật ETA/reroute", "Để đổi font chữ", "Để tăng độ sáng màn hình", "Để xóa dữ liệu"],
            "ans": 0,
            "why": "GPS live cần quyền vị trí để cập nhật chấm GPS, ETA và phát hiện lệch tuyến.",
        },
        {
            "cat": "Kỹ năng dùng app",
            "q": "Khi không muốn làm quiz, người dùng có bắt buộc phải làm không?",
            "opts": ["Có, nếu không thì không tìm đường được", "Không, quiz là phần học tự chọn", "Có, phải đúng hết mới dùng GPS", "Chỉ bắt buộc khi đi bộ"],
            "ans": 1,
            "why": "Quiz là module giáo dục tự chọn, không ảnh hưởng chức năng chính của app.",
        },
        {
            "cat": "Kỹ năng dùng app",
            "q": "Sau khi làm xong 5 câu quiz, lựa chọn hợp lý trong app là gì?",
            "opts": ["Có thể làm tiếp 5 câu khác hoặc thoát", "Bị khóa app", "Phải xóa lịch sử", "Bắt buộc báo cáo sự cố"],
            "ans": 0,
            "why": "Thiết kế này giúp học nhanh, không gây áp lực và phù hợp trải nghiệm tự chọn.",
        },
    ]

    total_questions = len(question_bank)
    per_round = 5

    st.subheader("📚 Học luật & An toàn giao thông")
    st.caption(
        f"Phần học tự chọn, không bắt buộc. Ngân hàng hiện có {total_questions} câu; "
        f"mỗi lượt hệ thống chọn ngẫu nhiên {per_round} câu để luyện an toàn, Net Zero và tư duy phản biện."
    )

    active_key = f"{key_prefix}_active"
    ids_key = f"{key_prefix}_ids"
    submitted_key = f"{key_prefix}_submitted"
    answers_key = f"{key_prefix}_answers"

    def _new_round():
        st.session_state[active_key] = True
        st.session_state[ids_key] = random.sample(range(total_questions), per_round)
        st.session_state[submitted_key] = False
        st.session_state[answers_key] = {}

    def _exit_quiz():
        st.session_state[active_key] = False
        st.session_state.pop(ids_key, None)
        st.session_state[submitted_key] = False
        st.session_state[answers_key] = {}

    if not st.session_state.get(active_key, False):
        st.markdown(
            '<div class="alert-info">📌 <b>Quiz là tự chọn:</b> Bạn có thể học nhanh 5 câu tình huống, '
            'sau đó làm tiếp bộ khác hoặc thoát để dùng app chính.</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            if st.button("▶️ Bắt đầu quiz 5 câu", key=f"{key_prefix}_start", type="primary"):
                _new_round()
                st.rerun()
        with c2:
            st.metric("Ngân hàng", f"{total_questions} câu")
        with c3:
            st.metric("Mỗi lượt", f"{per_round} câu")
        return

    if ids_key not in st.session_state or not st.session_state.get(ids_key):
        _new_round()

    sampled_ids = st.session_state.get(ids_key, [])
    sampled = [question_bank[i] for i in sampled_ids]

    st.markdown(
        '<div class="alert-success">🧠 <b>Đang làm quiz:</b> Chọn đáp án phù hợp nhất cho từng tình huống. '
        'Sau khi chấm điểm, app sẽ giải thích vì sao đáp án đó an toàn/bền vững hơn.</div>',
        unsafe_allow_html=True,
    )

    user_answers = {}
    for pos, item in enumerate(sampled, 1):
        q_key = f"{key_prefix}_q_{pos}_{sampled_ids[pos-1]}"
        st.markdown(f"**Câu {pos}.** _{item['cat']}_")
        choice = st.radio(
            item["q"],
            list(range(len(item["opts"]))),
            format_func=lambda idx, opts=item["opts"]: opts[idx],
            key=q_key,
            disabled=bool(st.session_state.get(submitted_key, False)),
        )
        user_answers[pos - 1] = choice

    if not st.session_state.get(submitted_key, False):
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✅ Chấm điểm quiz", key=f"{key_prefix}_submit", type="primary"):
                st.session_state[answers_key] = user_answers
                st.session_state[submitted_key] = True
                st.rerun()
        with c2:
            if st.button("↩️ Thoát quiz", key=f"{key_prefix}_exit_before"):
                _exit_quiz()
                st.rerun()
        return

    saved_answers = st.session_state.get(answers_key, user_answers)
    score = sum(1 for i, item in enumerate(sampled) if saved_answers.get(i) == item["ans"])
    pct = score / max(1, len(sampled))
    if score == len(sampled):
        level = "Rất tốt"
        msg = "Bạn hiểu tốt về an toàn, môi trường và cách đánh giá tuyến đường."
    elif score >= 3:
        level = "Khá tốt"
        msg = "Bạn đã nắm được ý chính, nên đọc thêm phần giải thích ở các câu chưa đúng."
    else:
        level = "Cần luyện thêm"
        msg = "Bạn nên làm thêm vài lượt để quen với các tình huống rủi ro thực tế."

    c1, c2, c3 = st.columns(3)
    c1.metric("Điểm", f"{score}/{len(sampled)}")
    c2.metric("Tỷ lệ đúng", f"{pct:.0%}")
    c3.metric("Mức hiểu biết", level)
    st.markdown(f'<div class="alert-info">💡 {msg}</div>', unsafe_allow_html=True)

    for pos, item in enumerate(sampled, 1):
        ans = saved_answers.get(pos - 1)
        ok = ans == item["ans"]
        css = "alert-success" if ok else "alert-warning"
        chosen_txt = item["opts"][ans] if ans is not None else "Chưa chọn"
        st.markdown(
            f'<div class="{css}"><b>Câu {pos}: {"Đúng" if ok else "Chưa đúng"}</b> · <i>{item["cat"]}</i><br>'
            f'Câu hỏi: {item["q"]}<br>'
            f'Bạn chọn: {chosen_txt}<br>'
            f'Đáp án hợp lý: {item["opts"][item["ans"]]}<br>'
            f'<span style="font-size:.9rem">{item["why"]}</span></div>',
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🔄 Làm tiếp 5 câu khác", key=f"{key_prefix}_next", type="primary"):
            _new_round()
            st.rerun()
    with c2:
        if st.button("✅ Thoát quiz", key=f"{key_prefix}_exit_after"):
            _exit_quiz()
            st.rerun()


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
                  forecast_segments=None,
                  gps_position=None,
                  enable_live_gps=False,
                  dest_lat=None,
                  dest_lon=None):

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
            level  = "🔴 Nguy hiểm" if sc >= RED_RISK_THRESHOLD else "🟠 Cảnh báo" if sc >= ORANGE_RISK_THRESHOLD else "🟡 Chú ý"

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
            _seg_score = _risk_score_float(seg.get("score", 0))
            # Theo ngưỡng mới: <40% bỏ qua; 40–64 vàng; 65–89 cam; >=90 đỏ.
            if _seg_score < YELLOW_RISK_THRESHOLD:
                continue  # bỏ qua các điểm an toàn để tránh spam bản đồ
            _seg_icon = _risk_level_icon(_seg_score)
            _seg_color = "#e53935" if _seg_score >= RED_RISK_THRESHOLD else "#fb8c00" if _seg_score >= ORANGE_RISK_THRESHOLD else "#fdd835"
            all_lats.append(seg["lat"])
            all_lons.append(seg["lon"])
            popup_html = (
                f"<div style='font-family:sans-serif;min-width:200px'>"
                f"<b>{_seg_icon} {seg.get('label','')}</b><br>"
                f"<span style='font-size:.85rem'>km {seg.get('route_km',0):.0f} · "
                f"ETA {seg.get('eta_text','')}</span><br>"
                f"<span style='font-size:.8rem'>Điểm rủi ro: {_seg_score:.0%}</span>"
                + ("<br><span style='font-size:.78rem;color:#555'>"
                   + "; ".join(seg.get("weather_alerts", [])) + "</span>" if seg.get("weather_alerts") else "")
                + "</div>"
            )
            folium.CircleMarker(
                [seg["lat"], seg["lon"]],
                radius=7,
                color=_seg_color,
                fill=True,
                fill_color=_seg_color,
                fill_opacity=0.85,
                weight=1,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f"{_seg_icon} km {seg.get('route_km',0):.0f} · ETA {seg.get('eta_text','')} · {seg.get('label','')}",
            ).add_to(m)

    # ── GPS hiện tại — chấm/hình nhân nhấp nháy + tô đoạn đã đi/chưa đi ──────
    # gps_position: {"lat":.., "lon":.., "progress_idx":.., "off_route":bool,
    #                 "reroute_polyline":[[lon,lat],...] hoặc None}
    if gps_position:
        g_lat = gps_position.get("lat")
        g_lon = gps_position.get("lon")
        g_progress_idx = gps_position.get("progress_idx", 0)
        g_offroute = gps_position.get("off_route", False)
        g_reroute_pl = gps_position.get("reroute_polyline")

        if g_lat is not None and g_lon is not None:
            all_lats.append(g_lat)
            all_lons.append(g_lon)

            # Tô lại đoạn ĐÃ ĐI (xám mờ) chồng lên tuyến gốc, dựa trên progress_idx
            if route_polyline and g_progress_idx > 0:
                try:
                    coords_past = [[p[1], p[0]] for p in route_polyline[:g_progress_idx + 1] if len(p) >= 2]
                    if len(coords_past) >= 2:
                        folium.PolyLine(
                            coords_past,
                            color="#9e9e9e", weight=7, opacity=0.6,
                            tooltip="Đoạn đã đi qua",
                            smooth_factor=0, line_cap="round", line_join="round",
                        ).add_to(m)
                except Exception:
                    pass

            # Nếu lệch tuyến và có tuyến tính lại → vẽ tuyến mới màu cam
            if g_offroute and g_reroute_pl and len(g_reroute_pl) >= 2:
                try:
                    coords_new = [[p[1], p[0]] for p in g_reroute_pl if len(p) >= 2]
                    all_lats += [p[1] for p in g_reroute_pl if len(p) >= 2]
                    all_lons += [p[0] for p in g_reroute_pl if len(p) >= 2]
                    folium.PolyLine(
                        coords_new, color="#ff6f00", weight=6, opacity=0.9,
                        tooltip="Tuyến tính lại (an toàn nhất)",
                        smooth_factor=0, line_cap="round", line_join="round",
                    ).add_to(m)
                except Exception:
                    pass

            pulse_color = "#e53935" if g_offroute else "#1a73e8"

            # Vòng nhấp nháy ngoài
            pulse_html = f"""
            <div style="
                width:30px; height:30px;
                border-radius:50%;
                background:transparent;
                border: 3px solid {pulse_color};
                margin-top:-15px; margin-left:-15px;
                animation: gpsnavpulse 1.6s infinite;
            "></div>
            <style>
            @keyframes gpsnavpulse {{
                0%   {{ transform:scale(0.8); opacity:1; }}
                70%  {{ transform:scale(2.2); opacity:0; }}
                100% {{ transform:scale(0.8); opacity:0; }}
            }}
            </style>"""
            folium.Marker(
                [g_lat, g_lon],
                icon=folium.DivIcon(html=pulse_html),
                z_index_offset=1000,
            ).add_to(m)

            # Chấm GPS / hình nhân ở giữa
            folium.CircleMarker(
                location=[g_lat, g_lon],
                radius=10,
                color=pulse_color, fill=True,
                fill_color=pulse_color, fill_opacity=0.9,
                weight=2,
                tooltip="📍 Vị trí của bạn (GPS)",
            ).add_to(m)
            folium.Marker(
                [g_lat, g_lon],
                icon=folium.DivIcon(html='<div style="font-size:22px;margin-top:-34px;text-align:center">🧍</div>'),
                tooltip="📍 Vị trí của bạn (GPS)",
            ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    pad = 0.05
    if all_lats and all_lons:
        m.fit_bounds([[min(all_lats)-pad, min(all_lons)-pad],
                      [max(all_lats)+pad, max(all_lons)+pad]])

    base_html = m._repr_html_()

    # ── Live GPS JS injection ─────────────────────────────────────────────────
    # Khi enable_live_gps=True, chèn JS watchPosition() vào HTML bản đồ.
    # Marker GPS được tạo và cập nhật HOÀN TOÀN phía client — không reload Streamlit,
    # không st_autorefresh, không mờ/chớp.
    if not enable_live_gps:
        return base_html

    _dest_lat = dest_lat if dest_lat is not None else lat2
    _dest_lon = dest_lon if dest_lon is not None else lon2

    # Serialize danger markers để JS có thể tính IoT state
    _dm_js = json.dumps([
        {
            "lat":   seg.get("lat", 0),
            "lon":   seg.get("lon", 0),
            "score": seg.get("score", 0),
            "label": seg.get("label", ""),
            "icon":  seg.get("icon", "⚠️"),
        }
        for seg in (danger_markers or [])
        if seg.get("lat") and seg.get("lon")
    ])

    # Serialize polyline để JS snap & tính progress
    _poly_js = json.dumps([
        [p[1], p[0]] for p in (route_polyline or []) if len(p) >= 2
    ])

    live_gps_js = f"""
<script>
(function() {{
  // ── Haversine distance (km) ───────────────────────────────────────────────
  function hav(lat1, lon1, lat2, lon2) {{
    var R = 6371.0, r = Math.PI/180;
    var dlat = (lat2-lat1)*r, dlon = (lon2-lon1)*r;
    var a = Math.sin(dlat/2)*Math.sin(dlat/2) +
            Math.cos(lat1*r)*Math.cos(lat2*r)*Math.sin(dlon/2)*Math.sin(dlon/2);
    return R * 2 * Math.asin(Math.sqrt(Math.max(0,a)));
  }}

  // ── Data từ Python (serialize 1 lần khi render) ──────────────────────────
  var DANGER_MARKERS = {_dm_js};
  var ROUTE_POLY     = {_poly_js};   // [[lat,lon], ...]
  var DEST_LAT       = {_dest_lat};
  var DEST_LON       = {_dest_lon};
  var OFFROUTE_KM    = 0.025;  // 25 m

  // ── Tìm Leaflet map object ────────────────────────────────────────────────
  function getLeafletMap() {{
    // Folium gắn map vào biến toàn cục có tên map_<uuid>
    for (var k in window) {{
      if (k.startsWith('map_') && window[k] && typeof window[k].addLayer === 'function') {{
        return window[k];
      }}
    }}
    return null;
  }}

  var gpsMarker    = null;
  var pulseCircle  = null;
  var watchId      = null;
  var mapObj       = null;
  var statusEl     = null;
  var arrived      = false;

  // ── Tạo status badge trong bản đồ ────────────────────────────────────────
  function createStatusBadge(map) {{
    var badge = L.control({{position: 'topright'}});
    badge.onAdd = function() {{
      var div = L.DomUtil.create('div', '');
      div.id  = 'gps-live-badge';
      div.style.cssText = 'background:white;border-radius:20px;padding:6px 14px;' +
        'font-family:sans-serif;font-size:.82rem;font-weight:600;' +
        'border:1.5px solid #1976d2;color:#1565c0;cursor:pointer;' +
        'box-shadow:0 2px 8px rgba(0,0,0,.2);';
      div.innerHTML = '📡 Bật GPS';
      div.onclick = function() {{ startGPS(map); }};
      statusEl = div;
      return div;
    }};
    badge.addTo(map);
  }}

  function setStatus(text, color) {{
    if (statusEl) {{
      statusEl.innerHTML = text;
      statusEl.style.color       = color || '#1565c0';
      statusEl.style.borderColor = color || '#1976d2';
    }}
  }}

  // ── Snap GPS lên polyline, trả về khoảng cách lệch tuyến ─────────────────
  function snapToRoute(lat, lon) {{
    if (!ROUTE_POLY.length) return {{idx: 0, dist: 0}};
    var bestIdx = 0, bestDist = 9999;
    for (var i = 0; i < ROUTE_POLY.length; i++) {{
      var d = hav(lat, lon, ROUTE_POLY[i][0], ROUTE_POLY[i][1]);
      if (d < bestDist) {{ bestDist = d; bestIdx = i; }}
    }}
    return {{idx: bestIdx, dist: bestDist}};
  }}

  // ── Tính IoT state từ GPS ─────────────────────────────────────────────────
  function calcIoTState(lat, lon) {{
    var nearestDist = 9999, nearestDanger = null;
    for (var i = 0; i < DANGER_MARKERS.length; i++) {{
      var d = hav(lat, lon, DANGER_MARKERS[i].lat, DANGER_MARKERS[i].lon);
      if (d < nearestDist) {{ nearestDist = d; nearestDanger = DANGER_MARKERS[i]; }}
    }}
    var score = (nearestDanger && nearestDist < 1.0) ? nearestDanger.score : 0;
    if (score >= 0.90) return 'danger';
    if (score >= 0.65 || nearestDist < 2.0) return 'warning';
    return 'safe';
  }}

  // ── Cập nhật marker GPS trên bản đồ ──────────────────────────────────────
  function updateGPSMarker(map, lat, lon) {{
    var snap     = snapToRoute(lat, lon);
    var offRoute = snap.dist > OFFROUTE_KM;
    var state    = calcIoTState(lat, lon);

    var color = offRoute ? '#e53935' : (state === 'danger' ? '#e53935' :
                                        state === 'warning' ? '#f9a825' : '#1a73e8');

    // Xóa marker cũ
    if (gpsMarker)   {{ map.removeLayer(gpsMarker);   gpsMarker   = null; }}
    if (pulseCircle) {{ map.removeLayer(pulseCircle); pulseCircle = null; }}

    // Vòng nhấp nháy (CSS animation trong DivIcon)
    var pulseIcon = L.divIcon({{
      className: '',
      html: '<div style="width:36px;height:36px;border-radius:50%;border:3px solid ' + color + ';' +
            'margin-top:-18px;margin-left:-18px;' +
            'animation:gpsnavpulse 1.6s infinite;"></div>' +
            '<style>@keyframes gpsnavpulse{{' +
            '0%{{transform:scale(.7);opacity:1}}' +
            '70%{{transform:scale(2.2);opacity:0}}' +
            '100%{{transform:scale(.7);opacity:0}}' +
            '}}</style>',
      iconSize:   [0, 0],
      iconAnchor: [0, 0],
    }});

    gpsMarker = L.marker([lat, lon], {{icon: pulseIcon, zIndexOffset: 1000}}).addTo(map);

    // Chấm chính + emoji người
    pulseCircle = L.circleMarker([lat, lon], {{
      radius:      10,
      color:       color,
      fillColor:   color,
      fillOpacity: 0.9,
      weight:      2,
    }}).addTo(map);
    pulseCircle.bindTooltip('📍 Vị trí của bạn (GPS live)');

    // Status badge
    var stateEmoji = state === 'danger' ? '🔴' : state === 'warning' ? '🟡' : '🟢';
    setStatus(stateEmoji + ' GPS ' + lat.toFixed(5) + ', ' + lon.toFixed(5), color);

    // Lưu localStorage để Python có thể đọc (cho IoT panel)
    try {{
      localStorage.setItem('tripsmart_gps', JSON.stringify({{
        lat: lat, lon: lon, acc: 0, ts: Date.now(),
        offRoute: offRoute, iotState: state,
      }}));
    }} catch(e) {{}}

    // Gửi postMessage lên parent (cho Streamlit biết nếu cần)
    try {{
      window.parent.postMessage({{
        type: 'tripsmart_gps',
        payload: {{lat, lon, acc: 0, ts: Date.now(), offRoute, iotState: state}},
      }}, '*');
    }} catch(e) {{}}

    // Kiểm tra đến nơi
    if (!arrived && hav(lat, lon, DEST_LAT, DEST_LON) < 0.05) {{
      arrived = true;
      setStatus('🎉 Đã đến điểm đến!', '#2e7d32');
      if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    }}
  }}

  // ── Bắt đầu watchPosition ─────────────────────────────────────────────────
  function startGPS(map) {{
    if (!navigator.geolocation) {{
      setStatus('❌ Trình duyệt không hỗ trợ GPS', '#b71c1c');
      return;
    }}
    setStatus('⏳ Đang chờ GPS…', '#f57c00');

    // Lần đầu: lấy ngay
    navigator.geolocation.getCurrentPosition(
      function(pos) {{ updateGPSMarker(map, pos.coords.latitude, pos.coords.longitude); }},
      function(err) {{ setStatus('❌ ' + (err.code===1 ? 'Bị từ chối quyền GPS' : 'Lỗi GPS'), '#b71c1c'); }},
      {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
    );

    // Theo dõi liên tục — cập nhật marker KHÔNG reload Streamlit
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = navigator.geolocation.watchPosition(
      function(pos) {{ updateGPSMarker(map, pos.coords.latitude, pos.coords.longitude); }},
      function(err) {{ setStatus('⚠️ Mất tín hiệu GPS', '#f57c00'); }},
      {{enableHighAccuracy: true, timeout: 10000, maximumAge: 1000}}
    );
  }}

  // ── Khởi động sau khi Leaflet map sẵn sàng ───────────────────────────────
  function init() {{
    mapObj = getLeafletMap();
    if (!mapObj) {{
      setTimeout(init, 200);
      return;
    }}
    createStatusBadge(mapObj);

    // Tự bật GPS nếu đã có quyền (saved localStorage < 30s)
    try {{
      var saved = localStorage.getItem('tripsmart_gps');
      if (saved) {{
        var p = JSON.parse(saved);
        if (Date.now() - p.ts < 30000) {{
          setTimeout(function() {{ startGPS(mapObj); }}, 500);
        }}
      }}
    }} catch(e) {{}}
  }}

  // Đợi DOM + Leaflet load xong
  if (document.readyState === 'complete') {{
    setTimeout(init, 300);
  }} else {{
    window.addEventListener('load', function() {{ setTimeout(init, 300); }});
  }}
}})();
</script>
"""

    # QUAN TRỌNG:
    # m._repr_html_() của Folium trả về một iframe. Nếu nối <script> vào base_html
    # thì script chạy ở trang cha của iframe, không nhìn thấy biến map_<uuid> của Leaflet.
    # Vì vậy phải nhúng script vào chính HTML gốc của Folium trước khi _repr_html_().
    try:
        from branca.element import Element
        m.get_root().html.add_child(Element(live_gps_js))
        return m._repr_html_()
    except Exception:
        # Fallback cũ: ít ổn định hơn, chỉ để tránh làm app crash nếu branca lỗi.
        if "</body>" in base_html:
            return base_html.replace("</body>", live_gps_js + "\n</body>")
        return base_html + live_gps_js


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
        "📚  Học luật & An toàn",
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
    st.markdown("**👨‍👩‍👧‍👦 Người thân SOS**")
    _render_sos_contacts_manager(prefix="sidebar_sos_family", require_hint=True)
    if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
        st.markdown("**🆘 SOS nhanh hành trình**")
        _render_one_tap_journey_sos_button(prefix="sidebar_fast_sos")
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
    st.caption("🆘 Trước khi bắt đầu dẫn đường GPS, hãy nhập số người thân ở sidebar để dùng SOS nhanh khi có sự cố.")

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

    # ── Tốc độ trung bình dùng để tính ETA / AI Risk Forecast ───────────────
    # Mặc định tự động theo phương tiện; chỉ hiện ô nhập khi người dùng muốn chỉnh.
    _default_eta_speed = _default_avg_speed_kmh_by_mode(mode)
    if "eta_custom_speed_enabled" not in st.session_state:
        st.session_state["eta_custom_speed_enabled"] = False
    if "eta_custom_speed_kmh" not in st.session_state:
        st.session_state["eta_custom_speed_kmh"] = _default_eta_speed

    with st.expander("⚙️ Tùy chọn ETA", expanded=False):
        st.checkbox(
            "Tùy chỉnh tốc độ trung bình để tính ETA",
            key="eta_custom_speed_enabled",
            help=(
                "Tắt: app tự dùng tốc độ theo phương tiện. "
                "Bật: mọi ETA và AI Risk Forecast sẽ dùng tốc độ bạn nhập."
            ),
        )
        if st.session_state.get("eta_custom_speed_enabled"):
            st.number_input(
                "Tốc độ trung bình dùng để tính ETA (km/h)",
                min_value=1.0, max_value=120.0, step=1.0,
                value=float(st.session_state.get("eta_custom_speed_kmh") or _default_eta_speed),
                key="eta_custom_speed_kmh",
                help="Áp dụng cho thời gian tuyến, Auto ETA, reroute và AI Risk Forecast.",
            )
            st.caption(f"Đang dùng tốc độ tùy chỉnh: {_format_speed_label(mode)}.")
        else:
            st.session_state["eta_custom_speed_kmh"] = _default_eta_speed
            st.caption(f"Đang dùng tốc độ mặc định theo phương tiện: {_format_default_speed_label(mode)}.")

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
        # Đóng băng tuỳ chọn tại đúng thời điểm bấm Tìm đường.
        # Nếu người dùng chuyển menu rồi quay lại, Streamlit sẽ rerun nhưng không làm đổi ngữ cảnh tuyến.
        st.session_state["pending_route_options"] = {
            "mode": mode,
            "poi_style": poi_style,
            "departure_dt_iso": departure_dt.isoformat(),
            "show_alt": bool(show_alt),
            "use_human": bool(use_human),
            "age": int(age),
            "travel_hour": int(travel_hour),
            "motion_sick": bool(motion_sick),
            "has_children": bool(has_children),
            "stress_level": int(stress_level),
            "eta_custom_speed_enabled": bool(st.session_state.get("eta_custom_speed_enabled", False)),
            "eta_custom_speed_kmh": float(st.session_state.get("eta_custom_speed_kmh") or _default_eta_speed),
        }
        # Xoá kết quả cũ khi search mới
        st.session_state.pop("last_routes", None)
        _clear_route_view_cache()

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

        _opts = st.session_state.get("pending_route_options") or {}
        mode = _opts.get("mode", mode)
        poi_style = _opts.get("poi_style", poi_style)
        departure_dt = _parse_session_datetime(_opts.get("departure_dt_iso"), departure_dt)
        show_alt = bool(_opts.get("show_alt", show_alt))
        use_human = bool(_opts.get("use_human", use_human))
        age = int(_opts.get("age", age))
        travel_hour = int(_opts.get("travel_hour", travel_hour))
        motion_sick = bool(_opts.get("motion_sick", motion_sick))
        has_children = bool(_opts.get("has_children", has_children))
        stress_level = int(_opts.get("stress_level", stress_level))
        # Dùng key nội bộ để áp dụng tốc độ ETA đã đóng băng khi bấm Tìm đường.
        # Không ghi vào key widget sau khi widget đã instantiate để tránh StreamlitAPIException.
        st.session_state["_route_eta_speed_override_active"] = True
        st.session_state["_route_eta_custom_speed_enabled"] = bool(_opts.get("eta_custom_speed_enabled", st.session_state.get("eta_custom_speed_enabled", False)))
        st.session_state["_route_eta_custom_speed_kmh"] = float(_opts.get("eta_custom_speed_kmh", st.session_state.get("eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode)))

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

        # Chuẩn hóa ETA theo tốc độ trung bình đang chọn:
        # mặc định: ô tô/xe máy 40 km/h, xe đạp 20 km/h, đi bộ 5 km/h;
        # nếu người dùng bật tùy chỉnh thì dùng tốc độ tùy chỉnh.
        _apply_avg_speed_timing_to_routes(routes, mode)

        labels = ["🚀 Nhanh nhất","⛽ Tiết kiệm","🌿 Cảnh đẹp"]
        for i, rt in enumerate(routes):
            if "label" not in rt:
                rt["label"] = labels[i] if i < len(labels) else f"Tuyến {i+1}"

        _save_route_runtime_options(mode, poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level)
        st.session_state.update({
            "last_origin": (lat1,lon1), "last_dest": (lat2,lon2),
            "last_mode": mode, "last_routes": routes,
        })

    if st.session_state.get("last_routes"):
        lat1, lon1 = st.session_state["last_origin"]
        lat2, lon2 = st.session_state["last_dest"]
        mode       = st.session_state.get("last_mode", mode)
        routes     = st.session_state.get("last_routes", [])
        poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level = _restore_route_runtime_options(
            poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level
        )
        _apply_avg_speed_timing_to_routes(routes, mode)

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
                risk_cls = ("risk-low" if item["avg_risk_score"] < YELLOW_RISK_THRESHOLD
                            else "risk-mid" if item["avg_risk_score"] < RED_RISK_THRESHOLD else "risk-high")
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
                risk_cls = ("risk-low" if risk_s < YELLOW_RISK_THRESHOLD
                            else "risk-mid" if risk_s < RED_RISK_THRESHOLD else "risk-high")
                risk_icon = _risk_level_icon(risk_s)
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

        # ── Cache phần phân tích tuyến để đổi menu rồi quay lại không bị tính lại ──
        _view_cache_key = _route_cache_key(polyline, route, mode, poi_style, departure_dt, selected)
        _view_cache = st.session_state.get("route_view_cache") or {}
        _cached_view = _view_cache.get(_view_cache_key) if _view_cache_key else None

        if _cached_view:
            colored_segs = _cached_view.get("colored_segs", [])
            analysis = _cached_view.get("analysis", {})
            danger_markers_raw = _cached_view.get("danger_markers_raw", [])
            danger_markers = _cached_view.get("danger_markers", [])
            rest_stops = _cached_view.get("rest_stops", [])
            route_risk_forecast = _cached_view.get("route_risk_forecast")
            warn_msg = _cached_view.get("warn_msg")
            if warn_msg:
                st.caption(warn_msg)
            st.caption("⚡ Đã dùng lại kết quả phân tích tuyến đã lưu — không tính lại khi quay lại trang Tìm đường.")
        else:
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
                warn_msg = None
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

            if _view_cache_key:
                st.session_state["route_view_cache"] = {
                    _view_cache_key: {
                        "colored_segs": colored_segs,
                        "analysis": analysis,
                        "danger_markers_raw": danger_markers_raw,
                        "danger_markers": danger_markers,
                        "rest_stops": rest_stops,
                        "route_risk_forecast": route_risk_forecast,
                        "warn_msg": warn_msg,
                        "pois": pois,
                    }
                }
                st.session_state["route_view_cache_key"] = _view_cache_key

        if _cached_view:
            pois = _cached_view.get("pois", [])

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
        m2.metric("⏱️ Thời gian",         route.get("duration_text","?"), help=f"Tính theo tốc độ TB {_format_speed_label(mode)}")
        m3.metric("🚨 Vùng trọng yếu",    len(danger_markers),
                  delta=f"lọc từ {len(danger_markers_raw)} điểm" if len(danger_markers_raw) != len(danger_markers) else None)
        m4.metric("☕ Điểm dừng nghỉ",    len(rest_stops))
        m5.metric("📍 Địa điểm",          len(pois))
        st.caption(f"⏱️ ETA đang tính theo tốc độ trung bình: {_format_speed_label(mode)} ({'ô tô/xe máy' if mode in ('car','motorbike') else 'xe đạp' if mode=='bike' else 'đi bộ' if mode=='walk' else mode}).")

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

        # ── AI Mobility Copilot: chỉ cảnh báo nhanh khi rủi ro cao trong 30 phút tới ─────
        try:
            _fc_for_quick_copilot = st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}
            _route_for_quick = dict(route or {})
            if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
                _route_for_quick["polyline"] = st.session_state.get("nav_polyline")
                _route_for_quick["distance_km"] = st.session_state.get("nav_distance_left_osrm") or st.session_state.get("auto_eta_distance_km") or _get_route_distance_km(route)
                _apply_avg_speed_timing(_route_for_quick, st.session_state.get("nav_mode", mode))
            _quick_copilot = _build_mobility_copilot_state(
                forecast=_fc_for_quick_copilot,
                route=_route_for_quick,
                danger_markers=danger_markers,
                rest_stops=rest_stops,
                mode=st.session_state.get("nav_mode", mode),
                nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
            )
            _quick_crit = _quick_copilot.get("critical_segment")
            if _quick_crit and st.session_state.get("nav_active"):
                st.markdown(
                    f'<div class="{_quick_copilot.get("rec_css","alert-warning")}">'
                    f'🧠 <b>Copilot phát hiện nguy cơ cao trong 30 phút tới:</b> '
                    f'{_quick_crit.get("label", "Đoạn rủi ro cao")} · ETA {_quick_crit.get("eta_text", "?")} · '
                    f'điểm {_quick_crit.get("score", 0):.0%}<br>'
                    f'<b>Khuyến nghị:</b> {_quick_copilot.get("recommendation", "")}. '
                    f'Mở tab <b>🧠 AI Mobility Copilot</b> để chọn đổi tuyến / nghỉ / vẫn đi tiếp.'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        # ── Bật/tắt dẫn đường theo GPS (gộp vào bản đồ chính) ────────────────
        # Không phụ thuộc _LIVE_NAV_OK để bật marker GPS client-side.
        # _LIVE_NAV_OK chỉ cần cho snap/reroute Python; marker live dùng JS trong bản đồ.
        if True:
            st.divider()
            _col_nav1, _col_nav2 = st.columns([3, 1])
            with _col_nav1:
                if not st.session_state.get("nav_active"):
                    if st.button(
                        "▶️ Bắt đầu dẫn đường theo GPS",
                        type="primary",
                        use_container_width=True,
                        key="btn_start_live_nav",
                    ):
                        if not _sos_get_family_contacts():
                            st.warning("⚠️ Vui lòng nhập ít nhất 1 số điện thoại người thân trong sidebar trước khi bắt đầu dẫn đường GPS để dùng SOS nhanh khi có sự cố.")
                            st.stop()
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
                        # Tạm dùng điểm xuất phát làm marker ban đầu; chưa coi là GPS thật
                        # cho tới khi trình duyệt đồng bộ được vị trí live.
                        st.session_state["nav_gps_lat"]       = lat1
                        st.session_state["nav_gps_lon"]       = lon1
                        st.session_state["nav_gps_ts"]        = 0.0
                        st.session_state["nav_gps_source"]    = "origin_initial"
                        st.session_state["nav_arrived"]       = False
                        st.session_state["nav_steps"]         = route.get("steps", [])
                        st.session_state["nav_distance_left"] = route.get("distance_km", 0)
                        st.session_state["nav_distance_left_osrm"] = route.get("distance_km", 0)
                        st.session_state["nav_step_text"]     = ""
                        for _eta_k in [
                            "auto_eta_last_ts", "auto_eta_distance_km", "auto_eta_duration_text",
                            "auto_eta_arrival", "auto_eta_updated_at", "auto_eta_forecast",
                            "auto_eta_ai_ready", "auto_eta_status", "auto_eta_ai_status",
                        ]:
                            st.session_state.pop(_eta_k, None)
                        st.rerun()
                else:
                    if st.button(
                        "⏹️ Dừng dẫn đường",
                        type="secondary",
                        use_container_width=True,
                        key="btn_stop_live_nav",
                    ):
                        for _k in list(st.session_state.keys()):
                            if _k.startswith("nav_"):
                                del st.session_state[_k]
                        st.rerun()
            with _col_nav2:
                st.caption("🛣️ Dẫn đường thời gian thực với GPS thật")

        # Rerun nhẹ mỗi 5 phút để Python lấy GPS mới rồi cập nhật ETA/AI Forecast.
        _maybe_schedule_nav_rerun()

        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            import time as _nav_time_mod
            _sync_nav_gps_from_browser(_nav_time_mod.time())

        # ── Cập nhật GPS & tính gps_position cho bản đồ chính ────────────────
        # GPS được cập nhật hoàn toàn qua JS watchPosition() trong HTML bản đồ.
        # Python không cần gọi get_geolocation() hay st_autorefresh nữa.
        # gps_position chỉ dùng để render HUD + IoT panel (dùng tọa độ từ session).
        gps_position = None
        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            ss = st.session_state

            # Đọc GPS cuối cùng từ session (đã lưu qua postMessage/localStorage-polling nếu cần)
            # Khi nav_active, bản đồ tự cập nhật marker via JS — không cần rerun ở đây
            g_lat = ss.get("nav_gps_lat")
            g_lon = ss.get("nav_gps_lon")

            if g_lat is not None and g_lon is not None:
                nav_polyline = ss.get("nav_polyline") or polyline
                dest_lat, dest_lon = ss.get("nav_dest", (lat2, lon2))

                # 2) Đến nơi?
                if _hav(g_lat, g_lon, dest_lat, dest_lon) < 0.05:
                    ss["nav_arrived"] = True
                    st.success("🎉 Bạn đã đến điểm đến!")

                # 3) Snap lên tuyến + tính tiến trình
                if _LIVE_NAV_OK and nav_polyline:
                    snap = _snap_to_route(g_lat, g_lon, nav_polyline)
                else:
                    snap = _find_nearest_segment(g_lat, g_lon, nav_polyline) if nav_polyline else {"segment_idx": 0, "dist_km": 0}
                    snap["idx"] = snap.get("idx", snap.get("segment_idx", 0))
                snap_idx = snap["idx"]
                off_dist = snap["dist_km"]

                if snap_idx >= ss.get("nav_max_progress", 0) - 2:
                    ss["nav_max_progress"] = max(ss.get("nav_max_progress", 0), snap_idx)
                    ss["nav_progress_idx"] = snap_idx
                else:
                    ss["nav_progress_idx"] = snap_idx

                # 4) Phát hiện lệch tuyến + tự tính lại
                is_offroute = ss.get("nav_offroute", False)
                if off_dist > 0.025 and not is_offroute:
                    ss["nav_offroute"] = True
                    is_offroute = True
                if off_dist <= 0.05 and is_offroute:
                    ss["nav_offroute"]     = False
                    ss["nav_reroute_pl"]   = None
                    ss["nav_reroute_risk"] = None
                    is_offroute = False

                import time as _time
                now = _time.time()
                need_reroute = (
                    is_offroute
                    and ss.get("nav_reroute_pl") is None
                    and (now - ss.get("nav_last_reroute", 0.0)) > 15
                )
                if need_reroute:
                    with st.spinner("🔄 Đang tính lại tuyến an toàn..."):
                        new_pl, new_risk, new_steps, _summary = _do_reroute(
                            router, risk_engine, g_lat, g_lon, dest_lat, dest_lon,
                            ss.get("nav_mode", mode),
                        )
                    if new_pl:
                        ss["nav_polyline"]     = new_pl
                        ss["nav_risk_segs"]    = new_risk
                        ss["nav_steps"]        = new_steps
                        ss["nav_progress_idx"] = 0
                        ss["nav_max_progress"] = 0
                        ss["nav_offroute"]     = False
                        ss["nav_reroute_pl"]   = None
                        ss["nav_last_reroute"] = now
                        try:
                            ss["nav_distance_left_osrm"] = float((_summary or {}).get("distance_km") or ss.get("nav_distance_left_osrm") or 0)
                        except Exception:
                            pass
                        nav_polyline = new_pl
                        is_offroute = False

                gps_position = {
                    "lat": g_lat,
                    "lon": g_lon,
                    "progress_idx": ss.get("nav_progress_idx", 0),
                    "off_route": is_offroute,
                    "reroute_polyline": ss.get("nav_reroute_pl"),
                }

                # Dùng polyline đang dẫn đường (có thể đã đổi sau reroute) để tô đoạn đã đi
                _gps_progress_polyline = nav_polyline
            else:
                _gps_progress_polyline = polyline
        else:
            _gps_progress_polyline = polyline

        # ── AUTO ETA: cập nhật mỗi 5 phút khi đang dẫn đường ────────────────
        import time as _time_mod
        _ss = st.session_state
        _now_ts = _time_mod.time()

        if _ss.get("nav_active") and not _ss.get("nav_arrived"):
            _last_eta_ts = _ss.get("auto_eta_last_ts", 0.0)
            _first_run   = (_last_eta_ts == 0.0)
            _due_for_eta = (_now_ts - _last_eta_ts) >= AUTO_ETA_INTERVAL_SEC
            if _first_run or _due_for_eta:
                with st.spinner("🔄 Đang tự động cập nhật ETA và AI Risk Forecast..."):
                    _run_auto_eta_update(
                        router=router,
                        risk_engine=risk_engine,
                        weather_api=weather_api,
                        dest_fallback=(lat2, lon2),
                        mode_fallback=mode,
                        now_ts=_now_ts,
                    )

        # ── Thẻ tóm tắt ETA nhỏ gọn (hiển thị khi đang dẫn đường) ───────────
        if _ss.get("nav_active") and not _ss.get("nav_arrived"):
            if _ss.get("auto_eta_last_ts", 0) > 0:
                _ai_status = _ss.get("auto_eta_ai_status") or ("✅ đã cập nhật" if _ss.get("auto_eta_ai_ready") else "⚠️ chưa sẵn sàng")
                _fc_now = _ss.get("auto_eta_forecast")
                _risk_txt = f"⚠️ Rủi ro: {_fc_now.get('overall_label','?')}" if _fc_now else ""
                _dist_val = _ss.get("auto_eta_distance_km")
                _dist_txt = f"{float(_dist_val):.1f} km" if _dist_val is not None else "?"
                st.markdown(
                    f'<div class="summary-bar" style="font-size:.85rem;padding:10px 16px">'
                    f'⏱️ <b>ETA tự động</b> · cập nhật mỗi 5 phút &nbsp;|&nbsp; '
                    f'📍 GPS: {_ss.get("nav_gps_source","?")} &nbsp;|&nbsp; '
                    f'🕒 Cập nhật lần cuối: {_ss.get("auto_eta_updated_at","—")} &nbsp;|&nbsp; '
                    f'🚗 Còn lại: {_dist_txt} &nbsp;|&nbsp; '
                    f'🏁 Dự kiến đến: {_ss.get("auto_eta_arrival","?")} &nbsp;|&nbsp; '
                    f'⚙️ Tốc độ ETA: {_format_speed_label(_ss.get("nav_mode", mode))} &nbsp;|&nbsp; '
                    f'🤖 AI Risk Model: {_ai_status}'
                    + (f' &nbsp;|&nbsp; {_risk_txt}' if _risk_txt else '') +
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                _status = _ss.get("auto_eta_status", "⏳ Đang chờ GPS thật để cập nhật ETA lần đầu.")
                st.caption(_status)


        # Nếu Auto ETA vừa tính lại tuyến GPS → đích, dùng tuyến còn lại mới nhất cho bản đồ.
        if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
            _gps_progress_polyline = st.session_state.get("nav_polyline")

        # BẢN ĐỒ — gộp tuyến hành trình + GPS hiện tại trong CÙNG 1 bản đồ
        st.subheader("🗺️ Bản đồ hành trình")
        _nav_active = st.session_state.get("nav_active", False)
        alt_routes_other = [rt for i,rt in enumerate(routes) if i != selected]
        map_html = make_full_map(
            lat1, lon1, lat2, lon2,
            colored_segments=colored_segs,
            route_polyline=_gps_progress_polyline if gps_position else polyline,
            alt_routes=alt_routes_other,
            danger_markers=danger_markers,
            rest_suggestions=rest_stops,
            pois=pois,
            reports=rpts,
            forecast_segments=(st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}).get("segments"),
            gps_position=gps_position,
            enable_live_gps=_nav_active,
            dest_lat=lat2,
            dest_lon=lon2,
        )
        components.html(map_html, height=620, scrolling=False)

        # ── HUD nhỏ khi đang dẫn đường ────────────────────────────────────────
        if gps_position:
            # "Còn lại" chỉ dùng OSRM/tuyến còn lại, tuyệt đối không dùng đường chim bay.
            _dist_left_osrm = st.session_state.get("nav_distance_left_osrm")
            _dist_left_txt = f"{float(_dist_left_osrm):.1f} km" if _dist_left_osrm is not None else "Đang cập nhật"
            _gps_ts = st.session_state.get("nav_gps_ts", 0.0)
            _gps_age_txt = "GPS mới" if _gps_ts else "chờ GPS thật"

            h1, h2, h3 = st.columns(3)
            h1.metric("📍 Còn lại", _dist_left_txt)
            h2.metric("📡 Lệch tuyến", "Có" if gps_position["off_route"] else "Không")
            h3.metric("🛰️ GPS", _gps_age_txt)

        # ── GPS cập nhật tự động qua JS watchPosition() trong bản đồ ──────────
        # Không cần st_autorefresh hay reload Streamlit — marker GPS di chuyển
        # hoàn toàn phía client, bản đồ không mờ/chớp.
        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            st.info("📡 GPS đang chạy — bấm **📡 Bật GPS** trên bản đồ. Marker chạy liên tục bằng JS; ETA/AI Forecast tự đồng bộ 5 phút/lần.")

        # ══════════════════════════════════════════════════════════════════════
        # 📌 CÔNG CỤ HÀNH TRÌNH — gom tất cả chức năng dưới bản đồ
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("### 📌 Công cụ hành trình")

        _tool_tab_copilot, _tool_tab_risk, _tool_tab_rest, _tool_tab_poi, _tool_tab_steps, _tool_tab_iot, _tool_tab_reroute, _tool_tab_eta, _tool_tab_impact = st.tabs([
            "🧠 AI Mobility Copilot",
            f"⚠️ Rủi ro ({len(danger_markers)})",
            f"☕ Điểm nghỉ ({len(rest_stops)})",
            f"📍 Địa điểm ({len(pois)})",
            "📋 Chỉ đường",
            "🚨 GPS / IoT",
            "🔄 Tuyến vòng",
            "⏱️ ETA & AI Forecast",
            "🌱 Tác động & Quiz",
        ])
        with _tool_tab_copilot:
            # Copilot dùng forecast mới nhất từ Auto ETA nếu có, nếu chưa có thì dùng forecast ban đầu.
            _fc_for_copilot = st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}
            _route_for_copilot = dict(route or {})
            if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
                _route_for_copilot["polyline"] = st.session_state.get("nav_polyline")
                _route_for_copilot["distance_km"] = st.session_state.get("nav_distance_left_osrm") or st.session_state.get("auto_eta_distance_km") or _get_route_distance_km(route)
                _apply_avg_speed_timing(_route_for_copilot, st.session_state.get("nav_mode", mode))

            _copilot = _build_mobility_copilot_state(
                forecast=_fc_for_copilot,
                route=_route_for_copilot,
                danger_markers=danger_markers,
                rest_stops=rest_stops,
                mode=st.session_state.get("nav_mode", mode),
                nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
            )
            _crit = _copilot.get("critical_segment") or {}
            st.session_state["copilot_critical_segment"] = _crit
            _render_mobility_copilot_state(_copilot)

            if st.session_state.get("copilot_last_action"):
                st.info(st.session_state.get("copilot_last_action"))

            st.markdown("**Hành động đề xuất**")
            cpa, cpb, cpc, cpd = st.columns(4)
            with cpa:
                if st.button("✅ Đồng ý đổi tuyến", key="copilot_accept_reroute", use_container_width=True):
                    ok, msg = _accept_copilot_reroute(
                        router=router,
                        risk_engine=risk_engine,
                        weather_api=weather_api,
                        mode_fallback=mode,
                        route_fallback=_route_for_copilot,
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
            with cpb:
                if st.button("⏸️ Nghỉ 15 phút", key="copilot_rest_15", use_container_width=True):
                    st.session_state["copilot_pending_rest_min"] = 15
            with cpc:
                if st.button("⏸️ Nghỉ 30 phút", key="copilot_rest_30", use_container_width=True):
                    st.session_state["copilot_pending_rest_min"] = 30
            with cpd:
                if st.button("⚠️ Vẫn đi tiếp", key="copilot_continue", use_container_width=True):
                    import time as _time
                    st.session_state["copilot_dismiss_until"] = _time.time() + 10 * 60
                    st.session_state["copilot_last_action"] = "⚠️ Bạn đã chọn vẫn đi tiếp. App sẽ tiếp tục giám sát rủi ro phía trước."
                    st.info(st.session_state["copilot_last_action"])

            _pending_rest = st.session_state.get("copilot_pending_rest_min")
            if _pending_rest:
                st.warning(f"Bạn có chắc muốn nghỉ {_pending_rest} phút rồi cập nhật lại ETA và AI Risk Forecast không?")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Xác nhận nghỉ và cập nhật", key="copilot_confirm_rest", use_container_width=True):
                        ok, msg = _accept_copilot_rest(
                            router=router,
                            risk_engine=risk_engine,
                            weather_api=weather_api,
                            mode_fallback=mode,
                            delay_min=int(_pending_rest),
                        )
                        st.session_state["copilot_pending_rest_min"] = None
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.warning(msg)
                with cc2:
                    if st.button("❌ Hủy", key="copilot_cancel_rest", use_container_width=True):
                        st.session_state["copilot_pending_rest_min"] = None
                        st.rerun()

            st.caption("Copilot không tự đổi tuyến. Hệ thống phát hiện nguy cơ → giải thích lý do → hỏi ý kiến → chỉ cập nhật tuyến/ETA/AI Forecast khi bạn xác nhận.")

        with _tool_tab_risk:
            if not danger_markers:
                st.markdown('<div class="alert-success">✅ Không phát hiện vùng nguy hiểm trọng yếu.</div>',
                            unsafe_allow_html=True)
            else:
                if len(danger_markers_raw) != len(danger_markers):
                    st.caption(f"Đã gom/lọc từ {len(danger_markers_raw)} điểm rủi ro thành {len(danger_markers)} vùng trọng yếu.")
            for seg in danger_markers:
                sc  = seg.get("score", 0)
                css = _risk_alert_css(sc)
                km_label = seg.get("km_text") or f"km {seg.get('route_km',0):.0f}"
                avg_txt = f" · TB {seg.get('avg_score', sc):.0%}" if seg.get("cluster_count", 1) > 1 else ""
                st.markdown(
                    f'<div class="{css}"><b>{seg.get("icon","⚠️")} {seg.get("label","")}</b>'
                    f'<span style="float:right;font-size:.83rem">{_risk_level_icon(sc)} {sc:.0%}{avg_txt} · {km_label}</span>'
                    f'<br>{seg.get("desc","")}</div>', unsafe_allow_html=True)

        with _tool_tab_rest:
            if not rest_stops: st.info("Không có điểm dừng nghỉ.")
            for rs in rest_stops:
                st.markdown(
                    f'<div class="alert-success"><b>{rs.get("icon","☕")} {rs.get("name","")}</b>'
                    f'<span style="float:right;font-size:.83rem">km {rs.get("route_km",0):.0f}</span>'
                    f'<br>{rs.get("desc","")}</div>', unsafe_allow_html=True)

        with _tool_tab_poi:
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

        with _tool_tab_steps:
            steps = route.get("steps",[])
            if not steps: st.info("Không có hướng dẫn (tuyến fallback).")
            for i,s in enumerate(steps,1):
                st.markdown(
                    f'<div class="step-box"><b>{i}.</b> {s["instruction"]} '
                    f'<span style="color:#888;font-size:.8em">— {s["distance_km"]} km · {s["duration_min"]} phút</span></div>',
                    unsafe_allow_html=True)

        with _tool_tab_iot:
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

                    # ── Đọc tọa độ GPS từ localStorage qua JS → Streamlit text_input ─
                    # JS tự điền ô input khi nhận được postMessage từ GPS component.
                    # User chỉ cần bấm "Cập nhật vị trí" để IoT panel tính lại — không
                    # cần reload toàn app, chỉ rerun khi user muốn.
                    gps_col1, gps_col2 = st.columns([3, 1])
                    with gps_col1:
                        _gps_input = st.text_input(
                            "📍 Tọa độ GPS hiện tại (tự điền hoặc nhập tay)",
                            value=st.session_state.get("gps_manual_input", ""),
                            placeholder="VD: 11.9404, 108.4583",
                            key="gps_coord_input",
                        )
                    with gps_col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🔄 Cập nhật vị trí", key="gps_refresh", use_container_width=True):
                            st.session_state["gps_manual_input"] = _gps_input
                            st.rerun()

                    # JS: lắng nghe postMessage từ GPS component → điền vào ô input
                    st.markdown("""
        <script>
        window.addEventListener('message', function(e) {
          if (e.data && e.data.type === 'tripsmart_gps') {
            var p = e.data.payload;
            var coord = p.lat.toFixed(6) + ', ' + p.lon.toFixed(6);
            var inputs = window.parent.document.querySelectorAll('input[type="text"]');
            for (var i = 0; i < inputs.length; i++) {
              var inp = inputs[i];
              if (inp.placeholder && inp.placeholder.includes('lat,lon') || inp.placeholder.includes('9404')) {
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

                        # ── IoT panel đã hiển thị — không cần auto-click nút nữa ────
                        # GPS cập nhật qua JS; user bấm "Cập nhật vị trí" khi muốn
                        # làm mới IoT panel (reroute, cảnh báo, v.v.)

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

                    if _cur_score >= RED_RISK_THRESHOLD:
                        _led_color="#e53935";_bg="#fff5f5";_border="#e53935"
                        _led_label="🔴 ĐỎ — Nguy hiểm";_buzzer="🔊 BẬT — Phát tiếng cảnh báo!"
                        _state_text="NGUY HIỂM"
                        _rec="⛔ Giảm tốc độ ngay, tăng cự ly với xe trước, sẵn sàng dừng khẩn cấp."
                    elif _cur_score >= ORANGE_RISK_THRESHOLD or _dist_to_danger < 5.0:
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
                            _di = next((i for i,p in enumerate(_sim_steps) if p.get("score",0)>=RED_RISK_THRESHOLD), None)
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
                            dot = _risk_level_icon(sc)
                            active = "background:#e3f2fd;border-left:4px solid #1976d2;font-weight:700" if i==_cur_idx else ""
                            st.markdown(
                                f'<div class="step-box" style="{active}">'
                                f'{dot} <b>Bước {i+1}</b> · {pt.get("icon","📍")} {pt.get("label","—")} '
                                f'· km {pt.get("route_km",0):.1f}'
                                + (f' · Rủi ro {sc:.0%}' if sc>0 else '')
                                + f'</div>', unsafe_allow_html=True)

        with _tool_tab_reroute:
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
                                _apply_avg_speed_timing(new_rt, mode_r)

                            if new_rt and not new_rt.get("fallback"):
                                st.session_state["last_incident_reroute"] = new_rt
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

        with _tool_tab_eta:
            # ── CẬP NHẬT ETA / DỰ BÁO RỦI RO THEO VỊ TRÍ HIỆN TẠI ───────────────────────
            st.subheader("⏱️ ETA tự động & AI Risk Forecast")
            if st.session_state.get("auto_eta_last_ts", 0):
                _fc_auto = st.session_state.get("auto_eta_forecast")
                st.success(
                    f"ETA tự động đã cập nhật lúc {st.session_state.get('auto_eta_updated_at','—')} · "
                    f"Còn lại {float(st.session_state.get('auto_eta_distance_km', 0) or 0):.1f} km · "
                    f"Dự kiến đến {st.session_state.get('auto_eta_arrival','?')}"
                )
                if _fc_auto:
                    _render_route_forecast(_fc_auto, datetime.now(), title="AI Risk Forecast theo GPS hiện tại")
                else:
                    st.info("AI Risk Model chưa có forecast tự động hoặc chưa sẵn sàng.")
            else:
                st.info(st.session_state.get("auto_eta_status", "Chưa có ETA tự động. Bật GPS trên bản đồ để app cập nhật lần đầu."))

            with st.expander("🛠️ Công cụ ETA thủ công / debug", expanded=False):
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
                                    _apply_avg_speed_timing(remaining_rt, mode_r)

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

        with _tool_tab_impact:
            _latest_reroute = st.session_state.get("last_incident_reroute")
            _render_env_social_impact(route, danger_markers, st.session_state.get("last_mode", mode), reroute_route=_latest_reroute)
            st.divider()
            _render_safety_quiz(key_prefix="trip_quiz")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. HỌC LUẬT & AN TOÀN
# ═══════════════════════════════════════════════════════════════════════════════
elif "Học luật" in menu:
    st.title("📚 Học luật & An toàn giao thông")
    st.markdown(
        '<div class="alert-info">🌱 Module giáo dục tự chọn gắn với Net Zero, an sinh xã hội và tư duy phản biện. '
        'Mỗi lượt hệ thống chọn ngẫu nhiên 5 câu từ ngân hàng 50 câu; làm xong có thể làm tiếp hoặc thoát.</div>',
        unsafe_allow_html=True,
    )
    _render_safety_quiz(key_prefix="standalone_quiz")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. KIỂM TRA RỦI RO
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
            col = "red" if sc >= RED_RISK_THRESHOLD else "orange" if sc >= YELLOW_RISK_THRESHOLD else "green"
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
        _contacts = _sos_get_family_contacts()
        if _contacts:
            _numbers = ",".join(_sos_normalize_phone_for_sms(c.get("phone")) for c in _contacts)
            _sms_body = _sos_message_template({"accident":"Tai nạn","medical":"Cấp cứu y tế","fire":"Cháy","stranded":"Mắc kẹt","general":"Khẩn cấp khác"}.get(etype, etype), lat, lon, msg)
            st.link_button("📨 Mở SMS gửi tất cả số người thân", _sos_build_sms_link(_numbers, _sms_body), use_container_width=True)
        else:
            st.warning("Bạn chưa nhập số người thân trong sidebar nên chưa thể mở SMS gửi người thân.")


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