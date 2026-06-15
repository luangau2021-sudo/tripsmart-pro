"""
live_navigation.py — TripSmart Pro · Live Navigation Mode
==========================================================
Chế độ dẫn đường thời gian thực với:
  - Chấm vị trí GPS hiện tại (nhấp nháy)
  - Tuyến đã đi → xám/mờ  |  chưa đi → màu gốc
  - Đi ngược → phần đã đi hiện lại
  - Lệch tuyến → tự tính lại tuyến mới (gần + an toàn nhất)
  - Cập nhật bản đồ liên tục

Gọi từ app.py:
    from live_navigation import render_live_navigation
    render_live_navigation(router, risk_engine)
"""

from __future__ import annotations

import math
import json
import time
import folium
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import get_geolocation
    _JS_EVAL_OK = True
except ImportError:
    _JS_EVAL_OK = False

# ─── Hằng số ────────────────────────────────────────────────────────────────

OFFROUTE_THRESHOLD_KM   = 0.08   # > 80 m → coi là lệch tuyến
REROUTE_COOLDOWN_SEC    = 15     # Chờ ít nhất 15 s giữa các lần tính lại
PROGRESS_SNAP_TOLERANCE = 0.05   # ±5% để tránh giật tiến trình khi GPS rung

# ─── Tiện ích tính khoảng cách ───────────────────────────────────────────────

def _hav(lat1, lon1, lat2, lon2) -> float:
    """Khoảng cách Haversine (km)."""
    R = 6371.0
    d = lambda a, b: math.radians(b - a)
    dlat, dlon = d(lat1, lat2), d(lon1, lon2)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def _snap_to_route(gps_lat: float, gps_lon: float, polyline: list) -> dict:
    """
    Tìm điểm gần nhất trên polyline (OSRM: [[lon,lat], ...]).
    Trả về {idx, lat, lon, dist_km, progress_ratio}
    """
    best_idx, best_dist = 0, 999.0
    for i, (lon_p, lat_p) in enumerate(polyline):
        d = _hav(gps_lat, gps_lon, lat_p, lon_p)
        if d < best_dist:
            best_dist, best_idx = d, i
    return {
        "idx"           : best_idx,
        "lat"           : polyline[best_idx][1],
        "lon"           : polyline[best_idx][0],
        "dist_km"       : round(best_dist, 4),
        "progress_ratio": best_idx / max(1, len(polyline) - 1),
    }


# ─── Xây dựng bản đồ dẫn đường ──────────────────────────────────────────────

def _build_nav_map(
    gps_lat: float,
    gps_lon: float,
    dest_lat: float,
    dest_lon: float,
    polyline: list,           # [[lon,lat], ...]
    progress_idx: int,        # index đến điểm hiện tại
    risk_segments: list,
    is_offroute: bool,
    reroute_polyline: list | None,
    reroute_risk: list | None,
) -> str:
    """Tạo HTML bản đồ Folium và trả về chuỗi HTML."""

    center = [gps_lat, gps_lon]
    m = folium.Map(location=center, zoom_start=15,
                   tiles="CartoDB positron", control_scale=True)

    # ── 1. Tuyến GỐC ────────────────────────────────────────────────────────
    if polyline:
        coords_all  = [[pt[1], pt[0]] for pt in polyline]
        coords_past = [[pt[1], pt[0]] for pt in polyline[:progress_idx + 1]]
        coords_ahead= [[pt[1], pt[0]] for pt in polyline[progress_idx:]]

        # Phần ĐÃ ĐI (xám mờ)
        if len(coords_past) >= 2:
            folium.PolyLine(
                coords_past,
                color="#aaaaaa", weight=5, opacity=0.45,
                tooltip="Đoạn đã đi qua"
            ).add_to(m)

        # Phần CHƯA ĐI (màu xanh dương rõ) — chỉ nếu KHÔNG lệch tuyến
        if not is_offroute and len(coords_ahead) >= 2:
            # Vẽ theo mức độ rủi ro
            _draw_risk_polyline(m, coords_ahead, risk_segments, progress_idx, len(polyline))

        # Điểm đến gốc (xám nhạt khi đang reroute)
        folium.CircleMarker(
            location=[dest_lat, dest_lon],
            radius=9,
            color="#888" if is_offroute else "#1a73e8",
            fill=True, fill_color="#fff",
            fill_opacity=0.9,
            tooltip="🏁 Điểm đến",
        ).add_to(m)
        folium.Marker(
            [dest_lat, dest_lon],
            icon=folium.DivIcon(html='<div style="font-size:22px;margin-top:-18px">🏁</div>'),
        ).add_to(m)

    # ── 2. Tuyến MỚI (khi reroute) ──────────────────────────────────────────
    if is_offroute and reroute_polyline and len(reroute_polyline) >= 2:
        coords_new = [[pt[1], pt[0]] for pt in reroute_polyline]
        _draw_risk_polyline(m, coords_new, reroute_risk or [], 0, len(reroute_polyline),
                            default_color="#ff6f00")

        # Vạch điểm đến của tuyến mới
        last = reroute_polyline[-1]
        folium.CircleMarker(
            location=[last[1], last[0]],
            radius=9, color="#ff6f00", fill=True,
            fill_color="#fff", fill_opacity=0.9,
            tooltip="🏁 Điểm đến (tuyến mới)",
        ).add_to(m)
        folium.Marker(
            [last[1], last[0]],
            icon=folium.DivIcon(html='<div style="font-size:22px;margin-top:-18px">🏁</div>'),
        ).add_to(m)

    # ── 3. Chấm GPS hiện tại (nhấp nháy) ────────────────────────────────────
    pulse_color = "#e53935" if is_offroute else "#1a73e8"
    folium.CircleMarker(
        location=[gps_lat, gps_lon],
        radius=10,
        color=pulse_color, fill=True,
        fill_color=pulse_color, fill_opacity=0.85,
        tooltip="📍 Vị trí của bạn",
    ).add_to(m)
    # Vòng nhấp nháy ngoài (dùng DivIcon + CSS)
    pulse_html = f"""
    <div style="
        width:28px; height:28px;
        border-radius:50%;
        background:transparent;
        border: 3px solid {pulse_color};
        margin-top:-14px; margin-left:-14px;
        animation: navpulse 1.6s infinite;
    "></div>
    <style>
    @keyframes navpulse {{
        0%   {{ transform:scale(0.8); opacity:1; }}
        70%  {{ transform:scale(2.0); opacity:0; }}
        100% {{ transform:scale(0.8); opacity:0; }}
    }}
    </style>"""
    folium.Marker(
        [gps_lat, gps_lon],
        icon=folium.DivIcon(html=pulse_html),
    ).add_to(m)

    return m._repr_html_()


def _draw_risk_polyline(m, coords_latlon, risk_segments, from_idx, total_pts,
                         default_color="#1a73e8"):
    """
    Vẽ polyline (list [[lat,lon]]) tô màu theo rủi ro nếu có risk_segments,
    ngược lại dùng default_color.
    """
    if not coords_latlon:
        return

    if not risk_segments:
        folium.PolyLine(
            coords_latlon, color=default_color, weight=6,
            opacity=0.85, tooltip="Tuyến phía trước"
        ).add_to(m)
        return

    # Chuyển risk_segments thành map: from_idx → color
    # risk_segments: [{"start_idx":..., "end_idx":..., "color":...}, ...]
    # Vẽ từng đoạn riêng (tối đa total_pts đoạn nhỏ)
    color_map = {}
    for seg in risk_segments:
        c = seg.get("color", default_color)
        for i in range(seg.get("start_idx", 0), seg.get("end_idx", 0) + 1):
            color_map[i] = c

    # Nhóm các điểm liên tiếp cùng màu
    if not coords_latlon:
        return
    current_color = color_map.get(from_idx, default_color)
    segment_pts   = [coords_latlon[0]]

    for i, pt in enumerate(coords_latlon[1:], 1):
        c = color_map.get(from_idx + i, default_color)
        if c == current_color:
            segment_pts.append(pt)
        else:
            if len(segment_pts) >= 2:
                folium.PolyLine(segment_pts, color=current_color,
                                weight=6, opacity=0.88).add_to(m)
            current_color = c
            segment_pts   = [coords_latlon[i-1], pt]

    if len(segment_pts) >= 2:
        folium.PolyLine(segment_pts, color=current_color,
                        weight=6, opacity=0.88).add_to(m)


# ─── Session-state helpers ────────────────────────────────────────────────────

def _init_nav_state():
    defaults = {
        "nav_active"        : False,
        "nav_origin"        : None,       # (lat, lon)
        "nav_dest"          : None,       # (lat, lon)
        "nav_dest_name"     : "",
        "nav_mode"          : "car",
        "nav_polyline"      : [],
        "nav_risk_segs"     : [],
        "nav_progress_idx"  : 0,
        "nav_max_progress"  : 0,          # để phát hiện đi ngược
        "nav_offroute"      : False,
        "nav_reroute_pl"    : None,
        "nav_reroute_risk"  : None,
        "nav_last_reroute"  : 0.0,        # timestamp
        "nav_gps_lat"       : None,
        "nav_gps_lon"       : None,
        "nav_arrived"       : False,
        "nav_distance_left" : None,
        "nav_step_text"     : "",
        "nav_steps"         : [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─── Tính tuyến mới khi lệch ─────────────────────────────────────────────────

def _do_reroute(router, risk_engine, gps_lat, gps_lon, dest_lat, dest_lon, mode):
    """
    Tính tuyến mới từ GPS hiện tại → đích, ưu tiên AN TOÀN NHẤT.
    Trả về (polyline, risk_segs, steps, summary_dict) hoặc (None,...) nếu lỗi.
    """
    try:
        # Lấy nhiều phương án nếu Router hỗ trợ
        try:
            if hasattr(router, "get_alternative_routes"):
                result = router.get_alternative_routes(
                    (gps_lat, gps_lon),
                    (dest_lat, dest_lon),
                    mode=mode,
                    count=3,
                )
            else:
                result = router.get_route(
                    (gps_lat, gps_lon),
                    (dest_lat, dest_lon),
                    mode=mode,
                )
        except TypeError:
            result = router.get_route(
                (gps_lat, gps_lon),
                (dest_lat, dest_lon),
                mode=mode,
            )

        routes = result if isinstance(result, list) else [result]

        if not routes or not routes[0]:
            return None, None, [], {}

        # Chọn tuyến AN TOÀN NHẤT (dùng risk_engine.compare_routes nếu có)
        best_route = routes[0]
        if len(routes) > 1 and risk_engine:
            try:
                enriched = risk_engine.compare_routes(routes)
                # Tuyến có avg_risk_score thấp nhất → an toàn nhất
                safest = min(enriched, key=lambda r: (r.get("avg_risk_score", 1),
                                                       r.get("danger_count", 0)))
                best_route = safest
            except Exception:
                pass

        polyline = best_route.get("polyline", [])
        steps    = best_route.get("steps", [])

        # Phân tích rủi ro tuyến mới
        risk_segs = []
        if risk_engine and polyline:
            try:
                analysis  = risk_engine.analyze_route(polyline)
                danger_sg = analysis.get("danger_segments", [])
                # Chuyển sang định dạng vẽ màu
                for seg in danger_sg:
                    score = seg.get("score", 0)
                    color = ("#b71c1c" if score >= 0.70 else
                             "#fb8c00" if score >= 0.55 else
                             "#fdd835" if score >= 0.40 else
                             "#43a047")
                    risk_segs.append({
                        "start_idx": seg.get("start_idx", 0),
                        "end_idx"  : seg.get("end_idx",   0),
                        "color"    : color,
                        "score"    : score,
                        "label"    : seg.get("label", ""),
                    })
            except Exception:
                pass

        summary = {
            "distance_km" : best_route.get("distance_km", 0),
            "duration_min": best_route.get("duration_min", 0),
            "duration_text": best_route.get("duration_text", ""),
            "distance_text": best_route.get("distance_text", ""),
        }
        return polyline, risk_segs, steps, summary

    except Exception as e:
        st.warning(f"⚠️ Reroute lỗi: {e}")
        return None, None, [], {}


# ─── Giao diện chính ─────────────────────────────────────────────────────────

def render_live_navigation(router=None, risk_engine=None, maps_api=None):
    """
    Entry-point chính — gọi từ app.py trong sidebar/tab.
    """
    _init_nav_state()

    st.markdown("## 🛣️ Live Navigation Mode")
    st.caption("Dẫn đường thời gian thực · GPS thật · Tự tính lại khi lệch tuyến")

    # ── Panel thiết lập (hiện khi chưa bắt đầu) ─────────────────────────────
    if not st.session_state.nav_active:
        _render_setup_panel(router, risk_engine, maps_api)
        return

    # ── Đã đến nơi ───────────────────────────────────────────────────────────
    if st.session_state.nav_arrived:
        st.success("🎉 **Bạn đã đến điểm đến!**")
        if st.button("🔄 Bắt đầu hành trình mới", key="nav_restart"):
            _reset_nav()
            st.rerun()
        return

    # ── Đang dẫn đường ───────────────────────────────────────────────────────
    _render_active_navigation(router, risk_engine)


# ─── Panel thiết lập ─────────────────────────────────────────────────────────

def _resolve_location(text: str, maps_api=None):
    """Geocode text → (lat, lon) hoặc None."""
    text = text.strip()
    if not text:
        return None
    # Thử parse "lat, lon"
    if "," in text:
        try:
            parts = text.split(",")
            return float(parts[0].strip()), float(parts[1].strip())
        except ValueError:
            pass
    # Dùng maps_api nếu có
    if maps_api:
        try:
            r = maps_api.geocode(text)
            if r and r.get("lat"):
                return r["lat"], r["lon"]
        except Exception:
            pass
    return None


def _render_setup_panel(router, risk_engine, maps_api):
    col1, col2 = st.columns(2)

    with col1:
        origin_txt = st.text_input(
            "📍 Điểm xuất phát",
            placeholder="Để trống = dùng GPS hiện tại",
            key="nav_setup_origin",
        )
    with col2:
        dest_txt = st.text_input(
            "🏁 Điểm đến",
            placeholder="Nhập tên hoặc lat, lon",
            key="nav_setup_dest",
        )

    mode = st.selectbox(
        "🚗 Phương tiện",
        ["car", "motorbike", "bike", "walk"],
        format_func=lambda x: {"car":"🚗 Ô tô","motorbike":"🏍️ Xe máy",
                                "bike":"🚲 Xe đạp","walk":"🚶 Đi bộ"}[x],
        key="nav_setup_mode",
    )

    if st.button("▶️ Bắt đầu dẫn đường", type="primary", key="nav_start_btn"):
        dest = _resolve_location(dest_txt, maps_api)
        if not dest:
            st.error("❌ Không xác định được điểm đến. Hãy nhập dạng `lat, lon`.")
            return

        # Lấy GPS hiện tại cho điểm xuất phát nếu để trống
        origin = None
        if origin_txt.strip():
            origin = _resolve_location(origin_txt, maps_api)

        if not origin:
            # Thử lấy GPS qua streamlit-js-eval
            if _JS_EVAL_OK:
                with st.spinner("📡 Đang lấy vị trí GPS..."):
                    geo = get_geolocation()
                if geo and geo.get("coords"):
                    origin = (geo["coords"]["latitude"], geo["coords"]["longitude"])
            if not origin:
                st.warning("⚠️ Chưa lấy được GPS. Hãy nhập toạ độ xuất phát.")
                return

        with st.spinner("🗺️ Đang tính tuyến đường..."):
            polyline, risk_segs, steps, summary = _do_reroute(
                router, risk_engine,
                origin[0], origin[1],
                dest[0], dest[1],
                mode,
            )

        if not polyline:
            st.error("❌ Không tính được tuyến. Kiểm tra kết nối mạng.")
            return

        # Lưu vào session_state
        st.session_state.nav_active       = True
        st.session_state.nav_origin       = origin
        st.session_state.nav_dest         = dest
        st.session_state.nav_dest_name    = dest_txt or f"{dest[0]:.4f}, {dest[1]:.4f}"
        st.session_state.nav_mode         = mode
        st.session_state.nav_polyline     = polyline
        st.session_state.nav_risk_segs    = risk_segs
        st.session_state.nav_steps        = steps
        st.session_state.nav_progress_idx = 0
        st.session_state.nav_max_progress = 0
        st.session_state.nav_gps_lat      = origin[0]
        st.session_state.nav_gps_lon      = origin[1]
        st.session_state.nav_distance_left= summary.get("distance_km", 0)
        st.session_state.nav_step_text    = steps[0].get("instruction", "") if steps else ""
        st.rerun()


# ─── Màn hình dẫn đường đang chạy ───────────────────────────────────────────

def _render_active_navigation(router, risk_engine):
    ss = st.session_state

    # ── Cập nhật GPS ─────────────────────────────────────────────────────────
    gps_lat, gps_lon = ss.nav_gps_lat, ss.nav_gps_lon

    if _JS_EVAL_OK:
        geo = get_geolocation()
        if geo and geo.get("coords"):
            new_lat = geo["coords"]["latitude"]
            new_lon = geo["coords"]["longitude"]
            # Chỉ cập nhật nếu dịch chuyển ≥ 3 m (tránh GPS rung)
            if gps_lat is None or _hav(gps_lat, gps_lon, new_lat, new_lon) > 0.003:
                gps_lat = new_lat
                gps_lon = new_lon
                ss.nav_gps_lat = gps_lat
                ss.nav_gps_lon = gps_lon

    if gps_lat is None:
        st.info("📡 Chờ tín hiệu GPS...")
        _show_stop_button()
        return

    polyline = ss.nav_polyline

    # ── Snap GPS lên tuyến ───────────────────────────────────────────────────
    snap      = _snap_to_route(gps_lat, gps_lon, polyline)
    snap_idx  = snap["idx"]
    off_dist  = snap["dist_km"]

    dest_lat, dest_lon = ss.nav_dest

    # Kiểm tra đến nơi (< 50 m đến điểm cuối)
    dist_to_dest = _hav(gps_lat, gps_lon, dest_lat, dest_lon)
    if dist_to_dest < 0.05:
        ss.nav_arrived = True
        st.rerun()

    # ── Cập nhật tiến trình ──────────────────────────────────────────────────
    is_offroute = ss.nav_offroute

    # Đi ngược: snap_idx < max_progress → phần đã đi hiện lại
    if snap_idx >= ss.nav_max_progress - 2:   # tolerance 2 điểm
        ss.nav_max_progress = max(ss.nav_max_progress, snap_idx)
        ss.nav_progress_idx = snap_idx
    else:
        # Đi ngược: chỉ cập nhật progress_idx (không tụt max)
        ss.nav_progress_idx = snap_idx

    # ── Phát hiện lệch tuyến ─────────────────────────────────────────────────
    now = time.time()
    if off_dist > OFFROUTE_THRESHOLD_KM and not is_offroute:
        ss.nav_offroute = True
        is_offroute     = True

    # Nếu snap lại trong tuyến (đã sửa lỗi)
    if off_dist <= OFFROUTE_THRESHOLD_KM * 0.6 and is_offroute:
        ss.nav_offroute     = False
        ss.nav_reroute_pl   = None
        ss.nav_reroute_risk = None
        is_offroute         = False

    # ── Tự tính lại tuyến khi lệch + cooldown ────────────────────────────────
    need_reroute = (
        is_offroute
        and ss.nav_reroute_pl is None
        and (now - ss.nav_last_reroute) > REROUTE_COOLDOWN_SEC
    )
    if need_reroute:
        with st.spinner("🔄 Đang tính lại tuyến an toàn..."):
            new_pl, new_risk, new_steps, new_summary = _do_reroute(
                router, risk_engine,
                gps_lat, gps_lon,
                dest_lat, dest_lon,
                ss.nav_mode,
            )
        if new_pl:
            ss.nav_reroute_pl   = new_pl
            ss.nav_reroute_risk = new_risk
            ss.nav_last_reroute = now
            # Chuyển hẳn sang tuyến mới
            ss.nav_polyline     = new_pl
            ss.nav_risk_segs    = new_risk
            ss.nav_steps        = new_steps
            ss.nav_progress_idx = 0
            ss.nav_max_progress = 0
            ss.nav_offroute     = False
            ss.nav_reroute_pl   = None
            is_offroute         = False

    # ── HUD thông tin ────────────────────────────────────────────────────────
    dist_left_km = _hav(gps_lat, gps_lon, dest_lat, dest_lon)

    # Xác định hướng dẫn bước hiện tại
    step_text = _get_current_step(ss.nav_steps, snap_idx, len(polyline))

    # Banner trạng thái
    if is_offroute:
        st.markdown(
            '<div style="background:#fff3e0;border:2.5px solid #ff6f00;border-radius:12px;'
            'padding:12px 16px;font-weight:700;font-size:1.05rem;color:#bf360c">'
            '⚠️ Bạn đang đi lệch tuyến — Đang tính tuyến mới...</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#e8f5e9;border:2px solid #43a047;border-radius:12px;'
            'padding:10px 16px;font-weight:600;color:#1b5e20">'
            '✅ Đang dẫn đường · Đi đúng tuyến</div>',
            unsafe_allow_html=True,
        )

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("📍 Còn lại", f"{dist_left_km:.1f} km")
    progress_pct = ss.nav_progress_idx / max(1, len(polyline) - 1)
    m2.metric("✅ Đã đi", f"{progress_pct:.0%}")
    m3.metric("📡 GPS off", f"{off_dist*1000:.0f} m")

    # Hướng dẫn bước
    if step_text:
        st.info(f"🔵 **{step_text}**")

    # ── Bản đồ ───────────────────────────────────────────────────────────────
    map_html = _build_nav_map(
        gps_lat, gps_lon,
        dest_lat, dest_lon,
        polyline,
        ss.nav_progress_idx,
        ss.nav_risk_segs,
        is_offroute,
        ss.nav_reroute_pl,
        ss.nav_reroute_risk,
    )
    components.html(map_html, height=480, scrolling=False)

    # ── Thanh tiến trình ─────────────────────────────────────────────────────
    st.progress(min(1.0, progress_pct))

    # ── Nút dừng + auto-refresh ──────────────────────────────────────────────
    col_stop, col_refresh = st.columns([2, 1])
    with col_stop:
        _show_stop_button()
    with col_refresh:
        refresh_sec = st.select_slider(
            "🔄 Cập nhật mỗi",
            options=[3, 5, 10, 15, 30],
            value=5,
            key="nav_refresh_interval",
        )

    # Auto-refresh bằng meta tag
    components.html(
        f'<meta http-equiv="refresh" content="{refresh_sec}">',
        height=0,
    )


def _get_current_step(steps: list, progress_idx: int, total_pts: int) -> str:
    """Trả về hướng dẫn bước phù hợp với tiến trình hiện tại."""
    if not steps:
        return ""
    ratio = progress_idx / max(1, total_pts - 1)
    step_idx = min(int(ratio * len(steps)), len(steps) - 1)
    step = steps[step_idx]
    return step.get("instruction") or step.get("text") or ""


def _show_stop_button():
    if st.button("⏹️ Dừng dẫn đường", key="nav_stop_btn", type="secondary"):
        _reset_nav()
        st.rerun()


def _reset_nav():
    keys = [k for k in st.session_state if k.startswith("nav_")]
    for k in keys:
        del st.session_state[k]