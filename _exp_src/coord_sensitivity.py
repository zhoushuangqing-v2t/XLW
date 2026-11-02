# -*- coding: utf-8 -*-
import math
import numpy as np, pandas as pd
from sklearn.cluster import KMeans
from pyproj import Transformer

def out_of_china(lon, lat):
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)
def _tl(x, y):
    r = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
    r += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
    r += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
    return r
def _tg(x, y):
    r = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
    r += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
    r += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
    return r
A, EE = 6378245.0, 0.00669342162296594323
def wgs2gcj(lng, lat):
    if out_of_china(lng, lat): return lng, lat
    dlat = _tl(lng - 105.0, lat - 35.0); dlng = _tg(lng - 105.0, lat - 35.0)
    rad = lat/180.0*math.pi; magic = math.sin(rad); magic = 1 - EE*magic*magic
    sm = math.sqrt(magic)
    dlat = (dlat*180.0)/((A*(1-EE))/(magic*sm)*math.pi)
    dlng = (dlng*180.0)/(A/sm*math.cos(rad)*math.pi)
    return lng + dlng, lat + dlat
def gcj2wgs(lng, lat):
    if out_of_china(lng, lat): return lng, lat
    wl, wt = lng, lat
    for _ in range(12):
        gl, gt = wgs2gcj(wl, wt)
        wl += lng - gl; wt += lat - gt
    return wl, wt

base = r"C:\Users\25798\Desktop\小论文claude code\_补充材料包\_8F25N\input"
c = pd.read_csv(base + r"\final_node_coordinates_574.csv")
c["node_id"] = c.node_id.astype(str)
mask = c.coordinate_source.eq("保留原始经纬度；原始坐标系未确认")
print("保留原始坐标的门店数:", int(mask.sum()))
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32650", always_xy=True)
to_wgs = Transformer.from_crs("EPSG:32650", "EPSG:4326", always_xy=True)

# 计算每个"保留原始"门店在 GCJ-02→WGS84 假设下的偏移量
shifts = []
for _, r in c[mask].iterrows():
    lon, lat = float(r.lon), float(r.lat)
    wlon, wlat = gcj2wgs(lon, lat)
    x1, y1 = to_utm.transform(lon, lat); x2, y2 = to_utm.transform(wlon, wlat)
    d = math.hypot(x2 - x1, y2 - y1)
    shifts.append(d)
shifts = np.array(shifts)
print("GCJ-02→WGS84 偏移: mean=%.1f m, median=%.1f m, max=%.1f m" % (shifts.mean(), np.median(shifts), shifts.max()))

# 构造"假设304家为GCJ-02→转WGS84"的替代坐标
c2 = c.copy()
for idx in c2[mask].index:
    lon, lat = float(c2.at[idx, "lon"]), float(c2.at[idx, "lat"])
    wlon, wlat = gcj2wgs(lon, lat)
    c2.at[idx, "lon"], c2.at[idx, "lat"] = wlon, wlat
c2.to_csv(r"C:\Users\25798\Desktop\小论文claude code\_exp_src\final_node_coordinates_574_gcj2wgs84.csv", index=False, encoding="utf-8-sig")

# 重新 K-means 聚类（K=4, random_state=42, n_init=20）
def cluster_coords(df):
    st = df[df.node_type == "store"]
    lon = st.lon.astype(float).to_numpy(); lat = st.lat.astype(float).to_numpy()
    x, y = to_utm.transform(lon, lat)
    km = KMeans(n_clusters=4, random_state=42, n_init=20).fit(np.column_stack([x, y]))
    cxy = km.cluster_centers_
    order = sorted(range(4), key=lambda j: (cxy[j, 0], cxy[j, 1]))
    labels = np.array([order.index(int(z)) for z in km.labels_])
    cxy = cxy[order]
    clon, clat = to_wgs.transform(cxy[:, 0], cxy[:, 1])
    cnt = np.bincount(labels, minlength=4)
    return clon, clat, cnt
print("\n=== 原始坐标聚类候选中心 ===")
clon0, clat0, cnt0 = cluster_coords(c)
for j in range(4):
    print(f"C{j+1}: lon={clon0[j]:.6f} lat={clat0[j]:.6f} count={cnt0[j]}")
print("\n=== 假设304家为GCJ-02→WGS84 后聚类候选中心 ===")
clon1, clat1, cnt1 = cluster_coords(c2)
for j in range(4):
    print(f"C{j+1}: lon={clon1[j]:.6f} lat={clat1[j]:.6f} count={cnt1[j]}")
print("\n=== 候选中心偏移 ===")
for j in range(4):
    x1, y1 = to_utm.transform(clon0[j], clat0[j]); x2, y2 = to_utm.transform(clon1[j], clat1[j])
    d = math.hypot(x2-x1, y2-y1)
    print(f"C{j+1}: 偏移 {d:.1f} m, 簇内门店数 {cnt0[j]} -> {cnt1[j]}")