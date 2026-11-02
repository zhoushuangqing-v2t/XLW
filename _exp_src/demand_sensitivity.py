# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r"C:\Users\25798\Desktop\小论文claude code\_exp_src")
import numpy as np, pandas as pd
from pathlib import Path
import solve_lrp_mixed_fleet_three_scenarios as S

input_dir = Path(r"C:\Users\25798\Desktop\小论文claude code\_补充材料包\_8F25N\input")
nodes = pd.read_csv(input_dir / "final_node_coordinates_574.csv", encoding="utf-8-sig")
nodes["node_id"] = nodes.node_id.astype(str)
ddf = pd.read_csv(input_dir / "store_demand_seed20261017.csv", encoding="utf-8-sig")
ddf["store_id"] = ddf.store_id.astype(str)
stores = ddf.store_id.tolist()
base_demand = dict(zip(ddf.store_id, ddf.daily_demand_t.astype(float)))
node_ids = nodes.node_id.tolist()
node_index = {nid: i for i, nid in enumerate(node_ids)}
matrices = {name: S.read_matrix(input_dir / f"distance_{name}_km.csv", node_ids)
            for name in ["unrestricted", "fuel_day", "nev_eligible"]}
baseline_perm = S.build_sweep_permutation(nodes, stores)
fleet = S.FLEET_SCENARIOS["8F_25N"]
seeds = S.DEFAULT_SEEDS
FLEET_CAP = 8*5.0 + 25*4.5

rows = []
for factor in [0.90, 0.95, 1.00, 1.05, 1.10]:
    demand = {sid: q*factor for sid, q in base_demand.items()}
    total_d = sum(demand.values())
    row = {"demand_factor": factor, "total_demand_t": round(total_d, 3),
           "fleet_load_utilization_pct": round(total_d/FLEET_CAP*100, 2)}
    # S1/S2 baseline
    base = S.decode_fleet(baseline_perm, np.zeros(4, dtype=np.int8), "S2", stores,
                          demand, nodes, node_index, matrices, fleet, policy=True)
    if not base["feasible"]:
        row.update({"S1_feasible": False, "S2_feasible": False,
                    "S1_cost": None, "S2_cost": None, "note": "S1/S2 baseline infeasible"})
    else:
        s1_df, _ = S.route_cost_table(base["routes"], False, matrices, node_index, "S1", "8F_25N", "BASE")
        s2_df, _ = S.route_cost_table(base["routes"], True,  matrices, node_index, "S2", "8F_25N", "BASE")
        s1c, s2c = S.route_components(s1_df), S.route_components(s2_df)
        row.update({
            "S1_feasible": True, "S2_feasible": True,
            "S1_cost": round(s1c["total_cost_yuan_day"], 2), "S1_dist": round(s1c["total_distance_km"], 2),
            "S1_fuel_routes": s1c["fuel_route_count"], "S1_nev_routes": s1c["nev_route_count"],
            "S2_cost": round(s2c["total_cost_yuan_day"], 2), "S2_dist": round(s2c["total_distance_km"], 2),
            "S2_fuel_routes": s2c["fuel_route_count"], "S2_nev_routes": s2c["nev_route_count"],
            "S2_vs_S1_pct": round((s2c["total_cost_yuan_day"]/s1c["total_cost_yuan_day"]-1)*100, 2),
        })
    # S3 GA x 3 seeds
    s3_costs, s3_dists, s3_opened, s3_feas, s3_fuel, s3_nev = [], [], [], [], [], []
    for seed in seeds:
        ga_result, best_ind, hist, evals = S.run_ga("S3", stores, demand, nodes, node_index,
                                                    matrices, fleet, seed, baseline_perm, 20, 30)
        if not ga_result["feasible"]:
            s3_feas.append(False); s3_costs.append(np.nan); s3_dists.append(np.nan)
            s3_opened.append("不可行"); s3_fuel.append(np.nan); s3_nev.append(np.nan)
            continue
        fr, _ = S.two_opt_all(ga_result["routes"], True, matrices, node_index)
        fr_df, _ = S.route_cost_table(fr, True, matrices, node_index, "S3", "8F_25N", str(seed))
        comps = S.route_components(fr_df, ga_result["candidate_open_cost"])
        s3_feas.append(True); s3_costs.append(comps["total_cost_yuan_day"]); s3_dists.append(comps["total_distance_km"])
        s3_opened.append(";".join(ga_result["opened_centers"]) or "无")
        s3_fuel.append(comps["fuel_route_count"]); s3_nev.append(comps["nev_route_count"])
    ok = [c for c in s3_costs if np.isfinite(c)]
    if ok:
        row.update({
            "S3_all_seeds_feasible": all(s3_feas),
            "S3_mean_cost": round(float(np.mean(ok)), 2),
            "S3_sd": round(float(np.std(ok, ddof=1)), 2) if len(ok) > 1 else 0.0,
            "S3_best": round(float(np.min(ok)), 2),
            "S3_worst": round(float(np.max(ok)), 2),
            "S3_mean_dist": round(float(np.mean([d for d in s3_dists if np.isfinite(d)])), 2),
            "S3_fuel_routes": ";".join(map(lambda x: str(int(x)) if np.isfinite(x) else "NA", s3_fuel)),
            "S3_nev_routes": ";".join(map(lambda x: str(int(x)) if np.isfinite(x) else "NA", s3_nev)),
            "S3_opened_centers": ";".join(sorted(set(x for x in s3_opened if x != "不可行"))),
            "S3_vs_S2_pct": round((1-float(np.mean(ok))/row["S2_cost"])*100, 2) if row.get("S2_cost") else None,
        })
    else:
        row.update({"S3_all_seeds_feasible": False, "S3_mean_cost": None})
    rows.append(row)
    print("DONE factor=%s total=%.3f S1=%s S2=%s S3_mean=%s opened=%s feas=%s" % (
        factor, total_d, row.get("S1_cost"), row.get("S2_cost"),
        row.get("S3_mean_cost"), row.get("S3_opened_centers"), row.get("S3_all_seeds_feasible")), flush=True)

df = pd.DataFrame(rows)
out = r"C:\Users\25798\Desktop\小论文claude code\_exp_src\demand_sensitivity.csv"
df.to_csv(out, index=False, encoding="utf-8-sig")
print("=== DEMAND SENSITIVITY RESULT ===")
print(df.to_string())
print("saved:", out)