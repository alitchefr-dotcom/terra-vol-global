# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Route-based transport emissions (GLEC Framework / ISO 14083, well-to-wheel).

Sea distance is estimated along waypoints (Suez / Red Sea or Cape of Good Hope), road distance from coordinates.
All factors are editable in the app; defaults:
  - Container vessel (other global, WTW):          0.0883 kg CO2e / TEU-km   (GLEC v3.1, 2024)
  - General cargo / MPP 10-20 kdwt, VLSFO (WTW):   0.0192 kg CO2e / t-km     (GLEC v3.0, 2023)
  - Articulated truck 34-40 t, container (WTW):    0.101  kg CO2e / t-km     (GLEC v3.2: TTW 0.078 + WTT 0.023)
"""
import math

GLEC_FACTORS = {"container_teu_km": 0.0883, "mpp_t_km": 0.0192, "truck_t_km": 0.101}

CHINA_POL_COORDS = {
    "Shanghai": (30.62, 122.07), "Ningbo-Zhoushan": (29.93, 121.85), "Ningbo": (29.93, 121.85),
    "Qingdao": (36.07, 120.32), "Shenzhen - Yantian": (22.57, 114.27), "Yantian": (22.57, 114.27),
    "Shenzhen - Shekou": (22.47, 113.90), "Guangzhou - Nansha": (22.75, 113.60), "Xingang / Tianjin": (38.98, 117.78),
    "Tianjin": (38.98, 117.78), "Xiamen": (24.45, 118.07),
}

# ---- waypoints
_ECS = (30.0, 123.5)          # East China Sea, off Shanghai
_TAIWAN_S = (21.8, 118.5)      # south of Taiwan
_SCS = (12.0, 110.5)           # South China Sea
_SG = (1.25, 104.0)            # Singapore Strait
_MALACCA_N = (5.9, 95.0)       # northern tip of Sumatra
_DONDRA = (5.6, 80.6)          # south of Sri Lanka
_SOCOTRA = (12.3, 53.5)
_BAB = (12.6, 43.4)            # Bab el-Mandeb
_RED_N = (27.5, 34.0)
_SUEZ = (29.9, 32.55)
_PORT_SAID = (31.4, 32.35)
_SUNDA = (-6.5, 105.0)
_INDIAN_S = (-25.0, 60.0)
_AGULHAS = (-35.5, 20.0)
_CAPE = (-34.6, 18.0)
_ANGOLA = (-15.0, 8.0)
_GULF_GUINEA = (0.0, -5.0)
_DAKAR = (14.7, -18.0)
_CANARY = (28.5, -16.0)
_GIB = (35.95, -5.6)
_ALBORAN = (36.5, -1.0)
_SICILY = (37.3, 11.5)
_CRETE_S = (34.6, 24.5)
_MATAPAN = (36.0, 22.5)
_AEGEAN = (38.5, 25.3)
_DARDANELLES = (40.1, 26.3)
_BOSPORUS = (41.2, 29.1)
_OTRANTO = (40.0, 18.9)
_ADRIATIC_N = (44.0, 13.8)
_SARDINIA_S = (38.6, 8.6)
_LIGURIAN = (43.2, 8.0)
_FINISTERRE = (43.3, -9.9)
_USHANT = (48.6, -5.6)
_DOVER = (51.0, 1.5)
_GERMAN_BIGHT = (54.0, 7.5)
_SKAGEN = (57.9, 10.7)
_ORESUND = (55.6, 12.8)
_BORNHOLM = (55.0, 15.5)
_GOTLAND_E = (57.3, 19.8)
_FINLAND_GULF = (59.7, 23.0)


def _hav(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _path_km(points):
    return sum(_hav(points[i], points[i + 1]) for i in range(len(points) - 1))


def _region(pod):
    p = (pod or "").lower()
    if any(k in p for k in ("israel", "haifa", "ashdod", "eilat")):
        return "eilat" if "eilat" in p else "east_med"
    if any(k in p for k in ("piraeus", "thessaloniki", "greece")):
        return "greece"
    if any(k in p for k in ("constan", "varna", "burgas")):
        return "black_sea"
    if any(k in p for k in ("koper", "trieste", "venice", "rijeka")):
        return "adriatic"
    if any(k in p for k in ("genoa", "marseille", "valencia", "barcelona")):
        return "west_med"
    if any(k in p for k in ("gdansk", "gdynia", "klaip", "riga", "muuga", "tallinn", "helsinki", "kotka")):
        return "baltic"
    return "north_europe"


def _asia_leg(pol):
    start = CHINA_POL_COORDS.get(pol, CHINA_POL_COORDS["Shanghai"])
    pts = [start]
    if start[0] > 25:           # northern / central China ports
        pts.append(_ECS)
    pts += [_TAIWAN_S, _SCS, _SG]
    return pts


def _tail_from_med_east(region, pod_xy):
    """Path from Port Said (Suez routing) to the POD."""
    if region in ("east_med",):
        return [pod_xy]
    if region == "greece":
        return [_CRETE_S, _MATAPAN, pod_xy] if pod_xy[1] < 23.0 else [_CRETE_S, (36.5, 25.5), pod_xy]
    if region == "black_sea":
        return [(35.5, 27.0), _AEGEAN, _DARDANELLES, _BOSPORUS, pod_xy]
    if region == "adriatic":
        return [_MATAPAN, _OTRANTO, _ADRIATIC_N, pod_xy]
    if region == "west_med":
        return [_SICILY, _SARDINIA_S, pod_xy] if pod_xy[1] > 3 else [_SICILY, _ALBORAN, pod_xy]
    # north Europe / Baltic: through Gibraltar
    return [_SICILY, _ALBORAN, _GIB] + _tail_from_gibraltar(region, pod_xy)


def _tail_from_gibraltar(region, pod_xy):
    """Path from Gibraltar (Cape routing) to the POD."""
    if region in ("east_med", "greece"):
        return [_ALBORAN, _SICILY, _CRETE_S, pod_xy]
    if region == "black_sea":
        return [_ALBORAN, _SICILY, _MATAPAN, _AEGEAN, _DARDANELLES, _BOSPORUS, pod_xy]
    if region == "adriatic":
        return [_ALBORAN, _SICILY, _OTRANTO, _ADRIATIC_N, pod_xy]
    if region == "west_med":
        return [_ALBORAN, pod_xy] if pod_xy[1] < 3 else [_ALBORAN, _LIGURIAN if pod_xy[1] > 7 else (42.5, 5.0), pod_xy]
    north = [_FINISTERRE, _USHANT, _DOVER]
    if region == "baltic":
        tail = [_GERMAN_BIGHT, _SKAGEN, _ORESUND, _BORNHOLM]
        if pod_xy[0] > 56.5:
            tail.append(_GOTLAND_E)
        if pod_xy[0] > 59:
            tail.append(_FINLAND_GULF)
        return north + tail + [pod_xy]
    if pod_xy[1] > 7:
        return north + [_GERMAN_BIGHT, pod_xy]
    return north + [pod_xy]


def sea_km(pol, pod, pod_xy, routing):
    """Estimated sea distance (km) from a Chinese port to the POD, via Suez / Red Sea or the Cape of Good Hope."""
    if not pod_xy:
        return None
    region = _region(pod)
    pts = _asia_leg(pol) + [_MALACCA_N, _DONDRA]
    if region == "eilat":
        return _path_km(pts + [_SOCOTRA, _BAB, (27.0, 34.6), pod_xy])
    if str(routing).startswith("Suez"):
        pts += [_SOCOTRA, _BAB, _RED_N, _SUEZ, _PORT_SAID] + _tail_from_med_east(region, pod_xy)
    else:
        pts = _asia_leg(pol) + [_SUNDA, _INDIAN_S, _AGULHAS, _CAPE, _ANGOLA, _GULF_GUINEA, _DAKAR, _CANARY, _GIB] \
              + _tail_from_gibraltar(region, pod_xy)
    return _path_km(pts)


def shipment_emissions(sea_distance_km, vessel_kind, teu, tonnes, road_km_dest, road_km_origin, f=None,
                       container_basis="teu"):
    """tCO2e split into sea and road for one shipment. vessel_kind: 'container' or 'mpp'.
    container_basis: 'teu' (GLEC default, per TEU-km) or 'mass' (per t-km, 10 t per TEU)."""
    f = f or GLEC_FACTORS
    if sea_distance_km is None:
        sea = 0.0
    elif vessel_kind == "container" and container_basis == "mass":
        sea = sea_distance_km * tonnes * (f["container_teu_km"] / 10.0) / 1000.0
    elif vessel_kind == "container":
        sea = sea_distance_km * teu * f["container_teu_km"] / 1000.0
    else:
        sea = sea_distance_km * tonnes * f["mpp_t_km"] / 1000.0
    road = ((road_km_dest or 0) + (road_km_origin or 0)) * tonnes * f["truck_t_km"] / 1000.0
    return {"sea_t": sea, "road_t": road, "total_t": sea + road}
