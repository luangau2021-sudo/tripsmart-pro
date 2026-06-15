from typing import List, Dict, Optional
from utils.helpers import haversine_distance, load_json
from utils.config import CULTURAL_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)

SAMPLE_POIS = [
    {"id":"poi_001","name":"Hồ Xuân Hương",      "lat":11.9404,"lon":108.4383,"category":"relaxation","tags":["lake","relaxation","scenic"],         "rating":4.7,"province":"Đà Lạt","type":"Hồ"},
    {"id":"poi_002","name":"Thác Datanla",         "lat":11.9049,"lon":108.4483,"category":"nature",    "tags":["waterfall","adventure","nature"],      "rating":4.5,"province":"Đà Lạt","type":"Thác"},
    {"id":"poi_003","name":"Chợ Đà Lạt",           "lat":11.9414,"lon":108.4415,"category":"food",      "tags":["market","food","culture"],             "rating":4.3,"province":"Đà Lạt","type":"Chợ"},
    {"id":"poi_004","name":"Thiền Viện Trúc Lâm",  "lat":11.8998,"lon":108.4141,"category":"culture",   "tags":["temple","culture","scenic"],           "rating":4.8,"province":"Đà Lạt","type":"Thiền viện"},
    {"id":"poi_005","name":"Mũi Né",               "lat":10.9432,"lon":108.2794,"category":"relaxation","tags":["beach","resort","relaxation"],         "rating":4.6,"province":"Bình Thuận","type":"Bãi biển"},
    {"id":"poi_006","name":"Phố cổ Hội An",        "lat":15.8801,"lon":108.3380,"category":"culture",   "tags":["heritage","culture","food","scenic"],  "rating":4.9,"province":"Quảng Nam","type":"Di sản"},
    {"id":"poi_007","name":"Vịnh Hạ Long",         "lat":20.9101,"lon":107.1839,"category":"nature",    "tags":["nature","boat","adventure","scenic"],  "rating":4.9,"province":"Quảng Ninh","type":"Vịnh"},
    {"id":"poi_008","name":"Sapa",                 "lat":22.3364,"lon":103.8438,"category":"adventure", "tags":["mountain","trekking","nature"],        "rating":4.7,"province":"Lào Cai","type":"Núi"},
    {"id":"poi_009","name":"Phong Nha - Kẻ Bàng",  "lat":17.5580,"lon":106.1427,"category":"nature",   "tags":["cave","ecotourism","adventure"],       "rating":4.8,"province":"Quảng Bình","type":"Hang động"},
    {"id":"poi_010","name":"Bà Nà Hills",           "lat":15.9973,"lon":107.9888,"category":"attraction","tags":["attraction","scenic","culture"],       "rating":4.5,"province":"Đà Nẵng","type":"Khu du lịch"},
    {"id":"poi_011","name":"Đảo Phú Quốc",         "lat":10.2897,"lon":103.9840,"category":"relaxation","tags":["beach","resort","relaxation","nature"],"rating":4.7,"province":"Kiên Giang","type":"Đảo"},
    {"id":"poi_012","name":"Ninh Bình – Tràng An", "lat":20.2510,"lon":105.9755,"category":"nature",   "tags":["scenic","boat","culture","ecotourism"], "rating":4.8,"province":"Ninh Bình","type":"Cảnh quan"},
    {"id":"poi_013","name":"Đèo Hải Vân",          "lat":16.2033,"lon":108.0847,"category":"scenic",   "tags":["scenic","mountain","adventure"],        "rating":4.6,"province":"Đà Nẵng","type":"Đèo"},
    {"id":"poi_014","name":"Chùa Bái Đính",        "lat":20.3250,"lon":105.8500,"category":"culture",  "tags":["temple","culture","heritage"],          "rating":4.6,"province":"Ninh Bình","type":"Chùa"},
    {"id":"poi_015","name":"Mekong – Cần Thơ",     "lat":10.0452,"lon":105.7469,"category":"culture",  "tags":["boat","food","culture","ecotourism"],   "rating":4.5,"province":"Cần Thơ","type":"Sông"},
    {"id":"poi_016","name":"Núi Bà Đen",           "lat":11.4167,"lon":106.0830,"category":"culture",  "tags":["mountain","temple","culture"],          "rating":4.4,"province":"Tây Ninh","type":"Núi"},
    {"id":"poi_017","name":"Bến Tre – Dừa nước",   "lat":10.2430,"lon":106.3756,"category":"ecotourism","tags":["ecotourism","boat","food"],            "rating":4.3,"province":"Bến Tre","type":"Sinh thái"},
    {"id":"poi_018","name":"Hồ Tuyền Lâm",         "lat":11.8668,"lon":108.4276,"category":"relaxation","tags":["lake","relaxation","nature"],         "rating":4.5,"province":"Đà Lạt","type":"Hồ"},
    {"id":"poi_019","name":"Nhà thờ Con Gà Đà Lạt","lat":11.9401,"lon":108.4394,"category":"culture", "tags":["heritage","culture","scenic"],          "rating":4.4,"province":"Đà Lạt","type":"Nhà thờ"},
    {"id":"poi_020","name":"Dinh Bảo Đại",         "lat":11.9200,"lon":108.4347,"category":"culture",  "tags":["heritage","culture","history"],         "rating":4.3,"province":"Đà Lạt","type":"Di tích"},
    {"id":"poi_021","name":"Thác Pongour",         "lat":11.6294,"lon":108.2100,"category":"nature",   "tags":["waterfall","nature","adventure"],       "rating":4.4,"province":"Lâm Đồng","type":"Thác"},
    {"id":"poi_022","name":"Bãi biển Nha Trang",   "lat":12.2451,"lon":109.1946,"category":"relaxation","tags":["beach","relaxation","resort"],        "rating":4.5,"province":"Khánh Hòa","type":"Bãi biển"},
    {"id":"poi_023","name":"Tháp Chàm Mỹ Sơn",    "lat":15.7630,"lon":108.1230,"category":"culture",  "tags":["heritage","culture","history"],         "rating":4.7,"province":"Quảng Nam","type":"Di sản"},
    {"id":"poi_024","name":"Hội quán Phúc Kiến",   "lat":15.8772,"lon":108.3274,"category":"culture",  "tags":["heritage","culture","food"],            "rating":4.6,"province":"Quảng Nam","type":"Di tích"},
    {"id":"poi_025","name":"Suối Tiên",            "lat":10.8677,"lon":106.8494,"category":"attraction","tags":["attraction","family","relaxation"],    "rating":4.2,"province":"TP.HCM","type":"Khu vui chơi"},
]

STYLE_TAGS = {
    "adventure":  ["trekking","mountain","waterfall","cave","boat","adventure"],
    "culture":    ["temple","museum","heritage","festival","culture","history"],
    "food":       ["restaurant","street_food","market","cafe","food"],
    "relaxation": ["beach","resort","spa","lake","relaxation"],
    "family":     ["park","zoo","amusement","beach","family","attraction"],
    "ecotourism": ["ecotourism","nature","boat","lake"],
    "scenic":     ["scenic","mountain","waterfall","boat"],
    "all":        [],   # không lọc
}


class POIEngine:
    TRAVEL_STYLES = STYLE_TAGS

    def __init__(self):
        self.cultural_data = load_json(CULTURAL_FILE) or {}
        self.pois = SAMPLE_POIS

    # ── Dọc tuyến đường ──────────────────────────────────────────────────────
    def get_pois_on_route(self, polyline: List, style: str = "all",
                          buffer_km: float = 8.0, max_results: int = 12) -> List[Dict]:
        """
        Tìm POI trong buffer_km km tính từ tuyến đường.
        polyline: list [[lon,lat], ...]
        """
        if not polyline:
            return []

        style_tags = STYLE_TAGS.get(style, [])
        results    = []
        # Sample polyline để tính nhanh
        sample = polyline[::max(1, len(polyline)//80)]

        for poi in self.pois:
            # Khoảng cách nhỏ nhất từ POI đến tuyến
            min_dist = min(
                haversine_distance(poi["lat"], poi["lon"], c[1], c[0])
                for c in sample
            )
            if min_dist > buffer_km:
                continue

            # Tính km từ đầu tuyến đến điểm gần nhất
            route_km = self._km_along_route(poi, sample)

            # Match score
            if style == "all" or not style_tags:
                match = 0.5
            else:
                overlap = len(set(poi.get("tags",[])) & set(style_tags))
                match   = overlap / len(style_tags) if style_tags else 0.5

            if match == 0 and style != "all":
                continue

            results.append({
                **poi,
                "dist_from_route_km": round(min_dist, 2),
                "route_km":           round(route_km, 1),
                "match_score":        round(match, 2),
                "final_score":        round(match * 0.55 + poi.get("rating", 3) / 5 * 0.45, 3),
            })

        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:max_results]

    # ── Gần điểm cụ thể ──────────────────────────────────────────────────────
    def get_pois_near_point(self, lat: float, lon: float,
                             style: str = "all", radius_km: float = 50.0,
                             max_results: int = 10) -> List[Dict]:
        """Tìm POI gần 1 điểm (dùng cho trang Điểm tham quan)."""
        style_tags = STYLE_TAGS.get(style, [])
        results    = []
        for poi in self.pois:
            dist = haversine_distance(lat, lon, poi["lat"], poi["lon"])
            if dist > radius_km:
                continue
            if style != "all" and style_tags:
                overlap = len(set(poi.get("tags",[])) & set(style_tags))
                if overlap == 0:
                    continue
                match = overlap / len(style_tags)
            else:
                match = 0.5

            results.append({
                **poi,
                "dist_from_route_km": round(dist, 2),
                "route_km":           0,
                "match_score":        round(match, 2),
            })

        results.sort(key=lambda x: x["dist_from_route_km"])
        return results[:max_results]

    def get_poi_detail(self, poi_id: str) -> Optional[Dict]:
        for poi in self.pois:
            if poi["id"] == poi_id:
                return {
                    **poi,
                    "story":      self._get_cultural_story(poi_id),
                    "local_food": self._get_local_food(poi.get("province","")),
                    "best_time":  "Tháng 11 – tháng 3 (mùa khô)",
                    "travel_tip": "Nên đến vào buổi sáng sớm để tránh đông đúc",
                }
        return None

    # ── Internal ─────────────────────────────────────────────────────────────
    def _km_along_route(self, poi: Dict, sample: List) -> float:
        """Ước tính km từ đầu tuyến đến điểm gần nhất với POI."""
        if not sample:
            return 0.0
        best_i, min_d = 0, float("inf")
        for i, c in enumerate(sample):
            d = haversine_distance(poi["lat"], poi["lon"], c[1], c[0])
            if d < min_d:
                min_d, best_i = d, i
        # Tính km đến điểm best_i
        km = 0.0
        for i in range(1, best_i + 1):
            km += haversine_distance(sample[i-1][1], sample[i-1][0],
                                     sample[i][1],   sample[i][0])
        return km

    def _get_cultural_story(self, poi_id: str) -> str:
        return self.cultural_data.get("stories", {}).get(
            poi_id, "Khám phá câu chuyện và lịch sử địa phương...")

    def _get_local_food(self, province: str) -> List[str]:
        food_map = {
            "Đà Lạt":      ["Bánh mì xíu mại","Bơ sáp Đà Lạt","Cà phê chồn"],
            "Hội An":      ["Cao lầu","Mì Quảng","Bánh mì Phượng"],
            "Quảng Nam":   ["Cao lầu","Mì Quảng","Bánh đập"],
            "Huế":         ["Bún bò Huế","Bánh nậm","Cơm hến"],
            "Hà Nội":      ["Phở Hà Nội","Bún chả","Bánh cuốn"],
            "TP.HCM":      ["Hủ tiếu Nam Vang","Bánh mì Sài Gòn","Cơm tấm"],
            "Đà Nẵng":     ["Mì Quảng","Bánh tráng cuốn thịt heo","Bún mắm nêm"],
            "Khánh Hòa":   ["Bún cá","Nem Ninh Hoà","Bánh căn"],
            "Cần Thơ":     ["Bánh cống","Lẩu mắm","Bún nước lèo"],
            "Quảng Bình":  ["Bánh canh","Chả mực","Cháo canh"],
        }
        return food_map.get(province, ["Ẩm thực địa phương đặc sắc"])