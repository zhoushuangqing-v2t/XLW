#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mixed-fleet three-scenario LRP experiment for the Wuhan case.

Scenario design:
S1: unrestricted road matrix; two existing depots fixed; baseline routes fixed.
S2: daytime restriction matrices; two existing depots fixed; same baseline routes as S1.
S3: daytime restrictions; candidate depots may be opened; GA jointly searches depot bits,
    store order/assignment and vehicle-route construction, followed by directed 2-opt.

Important methodological note:
No enterprise historical vehicle inventory or route records were supplied.
The fleet sizes below are explicit case-study assumptions, not observed company data.
S1/S2 are paired evaluations of one constructed baseline route plan, not actual
historical routes and not independently optimized route plans.
"""
from __future__ import annotations
import argparse, json, math, time, shutil, zipfile
from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd

VEHICLES = {
    "F": {"label": "燃油货车", "capacity_t": 5.0, "fixed_yuan": 280.0,
          "unit_yuan_km": 1.28, "max_route_km": float("inf")},
    "N": {"label": "新能源货车", "capacity_t": 4.5, "fixed_yuan": 230.0,
          "unit_yuan_km": 0.30, "max_route_km": 300.0},
}
CENTER_CAPACITY_T = {"existing_center": 100.0, "candidate_center": 60.0}
CANDIDATE_OPEN_COST_YUAN_DAY = 1000.0
BASE_SPEED_KMH = 25.0
DEFAULT_SEEDS = [20261023, 20262032, 20263041]
FLEET_SCENARIOS = {
    "5F_28N": {"F": 5, "N": 28},
    "8F_25N": {"F": 8, "N": 25},
    "12F_21N": {"F": 12, "N": 21},
}

def log(*args):
    print(time.strftime("[%H:%M:%S]"), *args, flush=True)

def read_matrix(path: Path, node_ids: list[str]) -> np.ndarray:
    df = pd.read_csv(path, index_col=0, encoding="utf-8-sig",
                     na_values=["INF", "inf", "Infinity", "infinity", ""])
    df.index = df.index.astype(str)
    df.columns = df.columns.astype(str)
    df = df.apply(pd.to_numeric, errors="coerce")
    missing_rows = sorted(set(node_ids) - set(df.index))
    missing_cols = sorted(set(node_ids) - set(df.columns))
    if missing_rows or missing_cols:
        raise ValueError(f"{path.name}: missing rows={missing_rows[:5]}, cols={missing_cols[:5]}")
    arr = df.loc[node_ids, node_ids].to_numpy(dtype=float)
    np.fill_diagonal(arr, 0.0)
    return arr

def mode_specs(policy: bool):
    if not policy:
        return {
            "F": {**VEHICLES["F"], "matrix": "unrestricted"},
            "N": {**VEHICLES["N"], "matrix": "unrestricted"},
        }
    return {
        "F": {**VEHICLES["F"], "matrix": "fuel_day"},
        "N": {**VEHICLES["N"], "matrix": "nev_eligible"},
    }

def build_sweep_permutation(nodes: pd.DataFrame, stores: list[str]) -> np.ndarray:
    """Fixed polar-angle ordering used only to construct the common S1/S2 baseline."""
    coord = nodes.set_index("node_id").loc[stores, ["lon", "lat"]]
    cx, cy = float(coord.lon.mean()), float(coord.lat.mean())
    angle = np.arctan2(coord.lat.to_numpy() - cy, coord.lon.to_numpy() - cx)
    radius = np.sqrt((coord.lon.to_numpy() - cx) ** 2 + (coord.lat.to_numpy() - cy) ** 2)
    order = coord.assign(_angle=angle, _radius=radius).sort_values(
        ["_angle", "_radius"], kind="mergesort"
    ).index.tolist()
    pos = {sid: i for i, sid in enumerate(stores)}
    return np.asarray([pos[sid] for sid in order], dtype=np.int32)

def decode_fleet(permutation, bits, scenario, stores, demand, nodes, node_index,
                 matrices, fleet, policy=True):
    """Constrained-first greedy decoder with explicit finite vehicle availability."""
    mode_map = mode_specs(policy)
    existing = nodes.loc[nodes.node_type.eq("existing_center"), "node_id"].astype(str).tolist()
    candidates = nodes.loc[nodes.node_type.eq("candidate_center"), "node_id"].astype(str).tolist()
    opened = [candidates[i] for i, b in enumerate(bits) if int(b) == 1] if scenario == "S3" else []
    active = existing + opened
    center_cap = {
        r.node_id: CENTER_CAPACITY_T[r.node_type]
        for r in nodes[nodes.node_type.isin(["existing_center", "candidate_center"])].itertuples()
    }
    center_load = {dc: 0.0 for dc in active}
    center_idx = {dc: node_index[dc] for dc in active}
    store_idx = {sid: node_index[sid] for sid in stores}
    routes = []
    mode_counts = {"F": 0, "N": 0}
    candidate_cost = len(opened) * CANDIDATE_OPEN_COST_YUAN_DAY

    permutation_store_ids = [stores[int(k)] for k in permutation]
    rank = {sid: k for k, sid in enumerate(permutation_store_ids)}

    # Prioritize stores with fewer feasible vehicle modes, then fewer feasible
    # center-mode combinations. Under the daytime matrix, fuel-inaccessible stores
    # must be assigned before flexible stores consume scarce NEV capacity.
    reach_count, mode_access_count = {}, {}
    for sid in stores:
        i = store_idx[sid]
        cnt = 0
        modes_access = set()
        for dc in active:
            j = center_idx[dc]
            for mode, spec in mode_map.items():
                M = matrices[spec["matrix"]]
                if np.isfinite(M[j, i]) and np.isfinite(M[i, j]):
                    if M[j, i] + M[i, j] <= spec["max_route_km"] + 1e-9:
                        cnt += 1
                        modes_access.add(mode)
        reach_count[sid] = cnt
        mode_access_count[sid] = len(modes_access)
    ordered = sorted(stores, key=lambda sid: (mode_access_count[sid], reach_count[sid], rank[sid]))

    for sid in ordered:
        q = float(demand[sid])
        i = store_idx[sid]
        best = None

        # Try appending to an existing route.
        for ri, r in enumerate(routes):
            dc = r["center_id"]
            if center_load[dc] + q > center_cap[dc] + 1e-9:
                continue
            spec = mode_map[r["mode"]]
            if r["load_t"] + q > spec["capacity_t"] + 1e-9:
                continue
            M = matrices[spec["matrix"]]
            last = store_idx[r["stores"][-1]]
            c = center_idx[dc]
            a, b, back = M[last, i], M[i, c], M[last, c]
            if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(back)):
                continue
            new_dist = r["distance_km"] - back + a + b
            if new_dist > spec["max_route_km"] + 1e-9:
                continue
            delta = spec["unit_yuan_km"] * (new_dist - r["distance_km"])
            cand = (delta, 0, ri, dc, r["mode"], new_dist)
            if best is None or cand < best:
                best = cand

        # Try opening a new route only if a vehicle of that type remains available.
        for dc in active:
            if center_load[dc] + q > center_cap[dc] + 1e-9:
                continue
            c = center_idx[dc]
            for mode, spec in mode_map.items():
                if mode_counts[mode] >= int(fleet[mode]):
                    continue
                if q > spec["capacity_t"] + 1e-9:
                    continue
                M = matrices[spec["matrix"]]
                outbound, inbound = M[c, i], M[i, c]
                if not (np.isfinite(outbound) and np.isfinite(inbound)):
                    continue
                dist = float(outbound + inbound)
                if dist > spec["max_route_km"] + 1e-9:
                    continue
                delta = spec["fixed_yuan"] + spec["unit_yuan_km"] * dist
                cand = (delta, 1, len(routes), dc, mode, dist)
                if best is None or cand < best:
                    best = cand

        if best is None:
            return {
                "feasible": False, "cost": float("inf"), "routes": [],
                "reason": f"No feasible insertion for store {sid}",
                "unserved_store": sid, "opened_centers": opened,
                "mode_counts": mode_counts,
            }

        delta, is_new, ri, dc, mode, dist = best
        if is_new:
            spec = mode_map[mode]
            routes.append({
                "center_id": dc, "mode": mode, "matrix": spec["matrix"],
                "stores": [sid], "load_t": q, "distance_km": dist,
                "fixed_cost_yuan": spec["fixed_yuan"],
                "unit_cost_yuan_km": spec["unit_yuan_km"],
            })
            mode_counts[mode] += 1
        else:
            r = routes[ri]
            r["stores"].append(sid)
            r["load_t"] += q
            r["distance_km"] = dist
        center_load[dc] += q

    served = [s for r in routes for s in r["stores"]]
    if len(served) != len(stores) or len(set(served)) != len(stores):
        return {"feasible": False, "cost": float("inf"), "routes": [],
                "reason": "Final store coverage check failed", "opened_centers": opened}
    if any(mode_counts[m] > int(fleet[m]) for m in fleet):
        return {"feasible": False, "cost": float("inf"), "routes": [],
                "reason": "Fleet availability exceeded", "opened_centers": opened}
    for dc, load in center_load.items():
        if load > center_cap[dc] + 1e-7:
            return {"feasible": False, "cost": float("inf"), "routes": [],
                    "reason": f"Center capacity exceeded: {dc}", "opened_centers": opened}
    for r in routes:
        spec = mode_map[r["mode"]]
        if r["load_t"] > spec["capacity_t"] + 1e-7 or r["distance_km"] > spec["max_route_km"] + 1e-7:
            return {"feasible": False, "cost": float("inf"), "routes": [],
                    "reason": f"Route constraint failed at {r['center_id']}", "opened_centers": opened}

    route_fixed = sum(r["fixed_cost_yuan"] for r in routes)
    variable_cost = sum(r["distance_km"] * r["unit_cost_yuan_km"] for r in routes)
    total_cost = candidate_cost + route_fixed + variable_cost
    return {
        "feasible": True, "cost": total_cost, "routes": routes,
        "opened_centers": opened, "center_load": center_load,
        "candidate_open_cost": candidate_cost, "route_fixed_cost": route_fixed,
        "variable_cost": variable_cost,
        "total_distance_km": sum(r["distance_km"] for r in routes),
        "mode_counts": mode_counts,
    }

def evaluate_route_sequence(center_id, store_seq, mode, policy, matrices, node_index):
    spec = mode_specs(policy)[mode]
    M = matrices[spec["matrix"]]
    ids = [node_index[center_id]] + [node_index[s] for s in store_seq] + [node_index[center_id]]
    legs = [M[a, b] for a, b in zip(ids[:-1], ids[1:])]
    if not all(np.isfinite(x) for x in legs):
        return float("inf")
    return float(sum(legs))

def two_opt_route(route, policy, matrices, node_index, max_passes=10):
    """Directed 2-opt steepest descent; accepts only feasible strict distance reductions."""
    mode = route["mode"]
    spec = mode_specs(policy)[mode]
    seq = route["stores"][:]
    dist = evaluate_route_sequence(route["center_id"], seq, mode, policy, matrices, node_index)
    passes, moves = 0, 0
    improved = True
    while improved and passes < max_passes:
        improved = False
        passes += 1
        best_seq, best_dist = None, dist
        n = len(seq)
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                d = evaluate_route_sequence(route["center_id"], cand, mode, policy, matrices, node_index)
                if d < best_dist - 1e-8 and d <= spec["max_route_km"] + 1e-8:
                    best_seq, best_dist = cand, d
        if best_seq is not None:
            seq, dist = best_seq, best_dist
            moves += 1
            improved = True
    new_route = dict(route)
    new_route["stores"] = seq
    new_route["distance_km"] = dist
    return new_route, {"passes": passes, "moves": moves}

def two_opt_all(routes, policy, matrices, node_index):
    optimized, logs = [], []
    for r in routes:
        rr, lg = two_opt_route(r, policy, matrices, node_index)
        optimized.append(rr)
        logs.append(lg)
    return optimized, logs

def route_cost_table(routes, policy, matrices, node_index, scenario, fleet_label, seed_label):
    mode_map = mode_specs(policy)
    rows, assignments = [], []
    for ri, r in enumerate(routes, 1):
        spec = mode_map[r["mode"]]
        dist = evaluate_route_sequence(r["center_id"], r["stores"], r["mode"], policy, matrices, node_index)
        load = float(r["load_t"])
        fixed = float(spec["fixed_yuan"])
        variable = float(spec["unit_yuan_km"] * dist)
        route_id = f"{scenario}_{fleet_label}_{seed_label}_R{ri:03d}"
        rows.append({
            "scenario": scenario, "fleet_scenario": fleet_label, "seed": seed_label,
            "route_id": route_id, "center_id": r["center_id"],
            "vehicle_mode": r["mode"], "vehicle_type": spec["label"],
            "matrix": spec["matrix"], "stop_count": len(r["stores"]),
            "route_load_t": load, "route_distance_km": dist,
            "fixed_cost_yuan": fixed, "variable_cost_yuan": variable,
            "route_total_cost_yuan": fixed + variable,
            "store_sequence": " -> ".join(r["stores"]),
        })
        for pos, sid in enumerate(r["stores"], 1):
            assignments.append({
                "scenario": scenario, "fleet_scenario": fleet_label, "seed": seed_label,
                "route_id": route_id, "store_id": sid, "center_id": r["center_id"],
                "vehicle_mode": r["mode"], "vehicle_type": spec["label"],
                "visit_order": pos,
            })
    return pd.DataFrame(rows), pd.DataFrame(assignments)

def route_qc(routes, policy, fleet, stores, demand, nodes, matrices, node_index):
    mode_map = mode_specs(policy)
    served = [s for r in routes for s in r["stores"]]
    mode_counts = {m: sum(r["mode"] == m for r in routes) for m in ["F", "N"]}
    center_load = {}
    finite, distance_ok, load_ok = True, True, True
    max_route = {"F": 0.0, "N": 0.0}
    max_load = {"F": 0.0, "N": 0.0}
    for r in routes:
        center_load[r["center_id"]] = center_load.get(r["center_id"], 0.0) + r["load_t"]
        spec = mode_map[r["mode"]]
        d = evaluate_route_sequence(r["center_id"], r["stores"], r["mode"], policy, matrices, node_index)
        finite = finite and np.isfinite(d)
        distance_ok = distance_ok and d <= spec["max_route_km"] + 1e-8
        load_ok = load_ok and r["load_t"] <= spec["capacity_t"] + 1e-8
        max_route[r["mode"]] = max(max_route[r["mode"]], d)
        max_load[r["mode"]] = max(max_load[r["mode"]], r["load_t"])
    cap_map = {r.node_id: CENTER_CAPACITY_T[r.node_type]
               for r in nodes[nodes.node_type.isin(["existing_center", "candidate_center"])].itertuples()}
    center_ok = all(v <= cap_map[c] + 1e-8 for c, v in center_load.items())
    return {
        "stores_served": len(served), "unique_stores": len(set(served)),
        "all_568_served_once": len(served) == len(stores) and len(set(served)) == len(stores) and set(served) == set(stores),
        "fuel_routes": mode_counts["F"], "nev_routes": mode_counts["N"],
        "fuel_fleet_limit": int(fleet["F"]), "nev_fleet_limit": int(fleet["N"]),
        "fleet_ok": mode_counts["F"] <= fleet["F"] and mode_counts["N"] <= fleet["N"],
        "center_loads": json.dumps(center_load, ensure_ascii=False),
        "center_capacity_ok": center_ok, "all_route_edges_finite": finite,
        "all_route_distance_ok": distance_ok, "all_route_load_ok": load_ok,
        "max_fuel_route_km": max_route["F"], "max_nev_route_km": max_route["N"],
        "max_fuel_load_t": max_load["F"], "max_nev_load_t": max_load["N"],
    }

def ox_crossover(p1, p2, rng):
    n = len(p1)
    a, b = sorted(rng.choice(n, size=2, replace=False).tolist())
    child = np.full(n, -1, dtype=np.int32)
    child[a:b + 1] = p1[a:b + 1]
    used = set(child[a:b + 1].tolist())
    fill = [int(x) for x in p2 if int(x) not in used]
    slots = [i for i in range(n) if child[i] == -1]
    for pos, val in zip(slots, fill):
        child[pos] = val
    return child

def mutate_perm(p, rng):
    q = p.copy()
    n = len(q)
    op = int(rng.integers(0, 3))
    a, b = sorted(rng.choice(n, size=2, replace=False).tolist())
    if op == 0:
        q[a], q[b] = q[b], q[a]
    elif op == 1:
        q[a:b + 1] = q[a:b + 1][::-1]
    else:
        val = q[b]
        q = np.delete(q, b)
        q = np.insert(q, a, val)
    return q.astype(np.int32)

def run_ga(name, stores, demand, nodes, node_index, matrices, fleet, seed,
           baseline_perm, population=20, generations=30):
    rng = np.random.default_rng(seed)
    candidates = nodes.loc[nodes.node_type.eq("candidate_center"), "node_id"].astype(str).tolist()
    n = len(stores)
    cache, history = {}, []
    evaluations = 0

    def evaluate(ind):
        nonlocal evaluations
        key = ind["bits"].tobytes() + ind["perm"].tobytes()
        if key not in cache:
            r = decode_fleet(ind["perm"], ind["bits"], "S3", stores, demand, nodes,
                             node_index, matrices, fleet, policy=True)
            score = r["cost"] if r["feasible"] else 1e15
            cache[key] = (score, r)
            evaluations += 1
        return cache[key]

    pop = [
        {"bits": np.zeros(len(candidates), dtype=np.int8), "perm": baseline_perm.copy()},
        {"bits": np.ones(len(candidates), dtype=np.int8), "perm": baseline_perm.copy()},
    ]
    while len(pop) < population:
        pop.append({
            "bits": rng.integers(0, 2, size=len(candidates), dtype=np.int8),
            "perm": rng.permutation(n).astype(np.int32),
        })

    best_score, best_ind, best_result, stale = float("inf"), None, None, 0
    for gen in range(generations + 1):
        scored = []
        for ind in pop:
            score, result = evaluate(ind)
            scored.append((score, ind, result))
        scored.sort(key=lambda x: x[0])
        if scored[0][0] + 1e-8 < best_score:
            best_score = scored[0][0]
            best_ind = {"bits": scored[0][1]["bits"].copy(), "perm": scored[0][1]["perm"].copy()}
            best_result = scored[0][2]
            stale = 0
        else:
            stale += 1
        feasible_scores = [x[0] for x in scored if x[0] < 1e14]
        history.append({
            "scenario": name, "seed": seed, "generation": gen,
            "best_cost_before_2opt_yuan_day": best_score if best_score < 1e14 else np.nan,
            "generation_best_cost_yuan_day": scored[0][0] if scored[0][0] < 1e14 else np.nan,
            "feasible_individuals": len(feasible_scores), "unique_evaluations": evaluations,
        })
        if gen == generations or stale >= 22:
            break
        elite_n = max(2, population // 10)
        new_pop = [{"bits": x[1]["bits"].copy(), "perm": x[1]["perm"].copy()} for x in scored[:elite_n]]
        while len(new_pop) < population:
            def tournament():
                ids = rng.choice(len(scored), size=min(3, len(scored)), replace=False)
                return min((scored[int(i)] for i in ids), key=lambda x: x[0])[1]
            p1, p2 = tournament(), tournament()
            child_perm = ox_crossover(p1["perm"], p2["perm"], rng)
            mask = rng.random(len(candidates)) < 0.5
            child_bits = np.where(mask, p1["bits"], p2["bits"]).astype(np.int8)
            if rng.random() < 0.12:
                child_bits[int(rng.integers(len(candidates)))] ^= 1
            if rng.random() < 0.75:
                child_perm = mutate_perm(child_perm, rng)
            new_pop.append({"bits": child_bits, "perm": child_perm})
        pop = new_pop
        if gen > 0 and gen % 10 == 0 and best_ind is not None:
            for _ in range(2):
                neigh = {"bits": best_ind["bits"].copy(),
                         "perm": mutate_perm(best_ind["perm"], rng)}
                ns, nr = evaluate(neigh)
                if ns < best_score:
                    best_score, best_ind, best_result = ns, neigh, nr
                    stale = 0
    return best_result, best_ind, pd.DataFrame(history), evaluations

def refine_candidate_bits(best_perm, stores, demand, nodes, node_index, matrices, fleet):
    """Exhaustively test all 16 candidate-center bitsets for the best GA permutation."""
    candidates = nodes.loc[nodes.node_type.eq("candidate_center"), "node_id"].astype(str).tolist()
    rows, best = [], None
    for mask in range(2 ** len(candidates)):
        bits = np.asarray([(mask >> i) & 1 for i in range(len(candidates))], dtype=np.int8)
        r = decode_fleet(best_perm, bits, "S3", stores, demand, nodes,
                         node_index, matrices, fleet, policy=True)
        if not r["feasible"]:
            rows.append({"bitmask": mask, "opened_centers": ";".join(r.get("opened_centers", [])),
                         "feasible": False, "total_cost_yuan_day": np.nan})
            continue
        routes2, logs = two_opt_all(r["routes"], True, matrices, node_index)
        route_df, _ = route_cost_table(routes2, True, matrices, node_index, "S3", "TEMP", f"MASK{mask}")
        total = float(route_df.route_total_cost_yuan.sum() + r["candidate_open_cost"])
        rows.append({"bitmask": mask, "opened_centers": ";".join(r["opened_centers"]),
                     "feasible": True, "route_operating_cost_yuan_day": float(route_df.route_total_cost_yuan.sum()),
                     "candidate_open_cost_yuan_day": r["candidate_open_cost"],
                     "total_cost_yuan_day": total,
                     "total_distance_km": float(route_df.route_distance_km.sum())})
        if best is None or total < best["cost"]:
            best = {"cost": total, "result": r, "routes": routes2,
                    "logs": logs, "bitmask": mask}
    return best, pd.DataFrame(rows)

def audit_candidate_bits_fast(best_perm, stores, demand, nodes, node_index, matrices, fleet):
    """Evaluate all 16 candidate-center bitsets without local search (fast conditional audit)."""
    candidates = nodes.loc[nodes.node_type.eq("candidate_center"), "node_id"].astype(str).tolist()
    rows = []
    for mask in range(2 ** len(candidates)):
        bits = np.asarray([(mask >> i) & 1 for i in range(len(candidates))], dtype=np.int8)
        r = decode_fleet(best_perm, bits, "S3", stores, demand, nodes,
                         node_index, matrices, fleet, policy=True)
        rows.append({
            "bitmask": mask, "opened_centers": ";".join(r.get("opened_centers", [])),
            "feasible": bool(r["feasible"]),
            "decoder_cost_before_2opt_yuan_day": float(r["cost"]) if r["feasible"] else np.nan,
            "route_count": len(r.get("routes", [])),
            "fuel_routes": r.get("mode_counts", {}).get("F", np.nan),
            "nev_routes": r.get("mode_counts", {}).get("N", np.nan),
        })
    return pd.DataFrame(rows)

def route_components(route_df, candidate_cost=0.0):
    return {
        "total_cost_yuan_day": float(route_df.route_total_cost_yuan.sum() + candidate_cost),
        "candidate_open_cost_yuan_day": float(candidate_cost),
        "vehicle_fixed_cost_yuan_day": float(route_df.fixed_cost_yuan.sum()),
        "distance_cost_yuan_day": float(route_df.variable_cost_yuan.sum()),
        "total_distance_km": float(route_df.route_distance_km.sum()),
        "route_count": int(len(route_df)),
        "fuel_route_count": int((route_df.vehicle_mode == "F").sum()),
        "nev_route_count": int((route_df.vehicle_mode == "N").sum()),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default=str(Path(__file__).resolve().parent / "input"))
    ap.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "results"))
    ap.add_argument("--population", type=int, default=20)
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--fleet-scenarios", default="5F_28N,8F_25N,12F_21N",
                    help="Comma-separated subset of 5F_28N,8F_25N,12F_21N")
    args = ap.parse_args()
    selected_labels = [x.strip() for x in args.fleet_scenarios.split(",") if x.strip()]
    selected_fleets = {k: FLEET_SCENARIOS[k] for k in selected_labels}
    if not selected_fleets:
        raise ValueError("No valid fleet scenarios selected")

    input_dir, out_dir = Path(args.input_dir), Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(input_dir / "final_node_coordinates_574.csv", encoding="utf-8-sig")
    nodes["node_id"] = nodes.node_id.astype(str)
    demand_df = pd.read_csv(input_dir / "store_demand_seed20261017.csv", encoding="utf-8-sig")
    demand_df["store_id"] = demand_df.store_id.astype(str)
    stores = demand_df.store_id.tolist()
    demand = dict(zip(demand_df.store_id, demand_df.daily_demand_t.astype(float)))
    node_ids = nodes.node_id.tolist()
    node_index = {nid: i for i, nid in enumerate(node_ids)}
    if len(stores) != 568 or len(nodes) != 574 or len(set(stores)) != 568:
        raise ValueError(f"Expected 568 stores and 574 nodes; got {len(stores)} and {len(nodes)}")
    matrices = {
        name: read_matrix(input_dir / f"distance_{name}_km.csv", node_ids)
        for name in ["unrestricted", "fuel_day", "nev_eligible"]
    }
    baseline_perm = build_sweep_permutation(nodes, stores)
    seeds = DEFAULT_SEEDS

    # Audit the policy-matrix vehicle reachability from the two existing centers.
    reach_rows = []
    for sid in stores:
        i = node_index[sid]
        fuel_ok, nev_ok = False, False
        for dc in ["D1", "D2"]:
            j = node_index[dc]
            Mf, Mn = matrices["fuel_day"], matrices["nev_eligible"]
            fuel_ok = fuel_ok or (np.isfinite(Mf[j, i]) and np.isfinite(Mf[i, j]))
            nev_ok = nev_ok or (np.isfinite(Mn[j, i]) and np.isfinite(Mn[i, j]))
        reach_rows.append({"store_id": sid, "fuel_reachable_from_existing": fuel_ok,
                           "nev_reachable_from_existing": nev_ok,
                           "reachable_modes": ";".join([m for m, ok in [("F", fuel_ok), ("N", nev_ok)] if ok])})
    reach_df = pd.DataFrame(reach_rows)
    reach_df.to_csv(out_dir / "vehicle_reachability_audit.csv", index=False, encoding="utf-8-sig")

    baseline_route_rows, baseline_assign_rows = [], []
    s3_route_rows, s3_assign_rows, history_rows = [], [], []
    check_rows, run_rows, summary_rows, candidate_sens_rows = [], [], [], []

    for fleet_label, fleet in selected_fleets.items():
        log(f"Fleet scenario {fleet_label}: F={fleet['F']}, N={fleet['N']}")
        # Fixed baseline is constructed once under daytime restrictions, then paired
        # evaluated under unrestricted and restricted matrices with no GA/2-opt.
        base = decode_fleet(baseline_perm, np.zeros(4, dtype=np.int8), "S2",
                            stores, demand, nodes, node_index, matrices, fleet, policy=True)
        if not base["feasible"]:
            raise RuntimeError(f"Baseline infeasible for {fleet_label}: {base.get('reason')}")
        s1_df, s1_assign = route_cost_table(base["routes"], False, matrices, node_index, "S1", fleet_label, "BASE")
        s2_df, s2_assign = route_cost_table(base["routes"], True, matrices, node_index, "S2", fleet_label, "BASE")
        baseline_route_rows.extend(s1_df.to_dict("records"))
        baseline_route_rows.extend(s2_df.to_dict("records"))
        baseline_assign_rows.extend(s1_assign.to_dict("records"))
        baseline_assign_rows.extend(s2_assign.to_dict("records"))

        s1c = route_components(s1_df)
        s2c = route_components(s2_df)
        check_rows.append({"scenario": "S1", "fleet_scenario": fleet_label, "seed": "BASE",
                           **route_qc(base["routes"], False, fleet, stores, demand, nodes, matrices, node_index)})
        check_rows.append({"scenario": "S2", "fleet_scenario": fleet_label, "seed": "BASE",
                           **route_qc(base["routes"], True, fleet, stores, demand, nodes, matrices, node_index)})

        s3_runs = []
        for seed in seeds:
            log(f"  S3 GA seed={seed}, pop={args.population}, gen={args.generations}")
            ga_result, best_ind, hist, evals = run_ga(
                f"S3_{fleet_label}", stores, demand, nodes, node_index, matrices,
                fleet, seed, baseline_perm, args.population, args.generations
            )
            history_rows.extend(hist.to_dict("records"))
            # Apply directed 2-opt to the GA-selected solution. The GA itself searches
            # both candidate-center bits and the store permutation.
            final_routes, opt_logs = two_opt_all(ga_result["routes"], True, matrices, node_index)
            final_route_df, final_assign_df = route_cost_table(
                final_routes, True, matrices, node_index, "S3", fleet_label, str(seed)
            )
            comps = route_components(final_route_df, ga_result["candidate_open_cost"])
            qc = route_qc(final_routes, True, fleet, stores, demand, nodes, matrices, node_index)
            check_rows.append({"scenario": "S3", "fleet_scenario": fleet_label, "seed": seed, **qc})
            s3_route_rows.extend(final_route_df.to_dict("records"))
            s3_assign_rows.extend(final_assign_df.to_dict("records"))
            two_opt_moves = int(sum(x["moves"] for x in opt_logs))
            run_rec = {
                "fleet_scenario": fleet_label, "seed": seed,
                "fleet_fuel_available": fleet["F"], "fleet_nev_available": fleet["N"],
                "ga_best_cost_before_2opt_yuan_day": float(ga_result["cost"]),
                "final_cost_after_2opt_yuan_day": comps["total_cost_yuan_day"],
                "total_distance_km": comps["total_distance_km"],
                "route_count": comps["route_count"],
                "fuel_route_count": comps["fuel_route_count"],
                "nev_route_count": comps["nev_route_count"],
                "opened_centers": ";".join(ga_result["opened_centers"]),
                "candidate_open_cost_yuan_day": comps["candidate_open_cost_yuan_day"],
                "vehicle_fixed_cost_yuan_day": comps["vehicle_fixed_cost_yuan_day"],
                "distance_cost_yuan_day": comps["distance_cost_yuan_day"],
                "ga_unique_evaluations": evals,
                "directed_2opt_moves": two_opt_moves,
                "best_bitmask": int(sum((int(v) << i) for i, v in enumerate(best_ind["bits"]))),
            }
            run_rows.append(run_rec)
            s3_runs.append(run_rec)
            # Store the best GA permutation and route result for one final center-bit audit.
            if not hasattr(main, "_best_perm_by_fleet"):
                main._best_perm_by_fleet = {}
            current = main._best_perm_by_fleet.get(fleet_label)
            if current is None or comps["total_cost_yuan_day"] < current["cost"]:
                main._best_perm_by_fleet[fleet_label] = {
                    "cost": comps["total_cost_yuan_day"], "seed": seed,
                    "perm": best_ind["perm"].copy(), "bits": best_ind["bits"].copy(),
                    "routes": final_routes, "candidate_open_cost": ga_result["candidate_open_cost"],
                }

        s3_costs = [x["final_cost_after_2opt_yuan_day"] for x in s3_runs]
        s3_dists = [x["total_distance_km"] for x in s3_runs]
        summary_rows.append({
            "fleet_scenario": fleet_label, "fuel_available": fleet["F"], "nev_available": fleet["N"],
            "total_fleet_size": fleet["F"] + fleet["N"],
            "S1_baseline_cost_yuan_day": s1c["total_cost_yuan_day"],
            "S1_baseline_distance_km": s1c["total_distance_km"],
            "S1_fuel_routes": s1c["fuel_route_count"], "S1_nev_routes": s1c["nev_route_count"],
            "S2_baseline_cost_yuan_day": s2c["total_cost_yuan_day"],
            "S2_baseline_distance_km": s2c["total_distance_km"],
            "S2_fuel_routes": s2c["fuel_route_count"], "S2_nev_routes": s2c["nev_route_count"],
            "S2_minus_S1_yuan_day": s2c["total_cost_yuan_day"] - s1c["total_cost_yuan_day"],
            "S2_increase_vs_S1_pct": (s2c["total_cost_yuan_day"] / s1c["total_cost_yuan_day"] - 1) * 100,
            "S3_mean_cost_yuan_day": float(np.mean(s3_costs)),
            "S3_sd_yuan_day": float(np.std(s3_costs, ddof=1)),
            "S3_best_cost_yuan_day": float(np.min(s3_costs)),
            "S3_worst_cost_yuan_day": float(np.max(s3_costs)),
            "S3_mean_distance_km": float(np.mean(s3_dists)),
            "S3_best_distance_km": float(s3_dists[int(np.argmin(s3_costs))]),
            "S2_minus_S3_mean_yuan_day": s2c["total_cost_yuan_day"] - float(np.mean(s3_costs)),
            "S3_mean_reduction_vs_S2_pct": (1 - float(np.mean(s3_costs)) / s2c["total_cost_yuan_day"]) * 100,
            "S1_minus_S3_mean_yuan_day": s1c["total_cost_yuan_day"] - float(np.mean(s3_costs)),
            "S3_mean_reduction_vs_S1_pct": (1 - float(np.mean(s3_costs)) / s1c["total_cost_yuan_day"]) * 100,
        })

    # Full conditional audit of all 16 candidate-center bitsets for the best GA
    # permutation of each fleet structure. Each bitset is decoded and then receives
    # the same directed 2-opt local search before costs are compared.
    best_perm_by_fleet = getattr(main, "_best_perm_by_fleet", {})
    bitset_best_by_fleet = {}
    for fleet_label, fleet in selected_fleets.items():
        best_info = best_perm_by_fleet[fleet_label]
        best_audit, bit_df = refine_candidate_bits(
            best_info["perm"], stores, demand, nodes, node_index, matrices, fleet
        )
        bit_df.insert(0, "fleet_scenario", fleet_label)
        bit_df.insert(1, "seed", best_info["seed"])
        candidate_sens_rows.extend(bit_df.to_dict("records"))
        bitset_best_by_fleet[fleet_label] = int(best_audit["bitmask"])
        best_run = min(
            [r for r in run_rows if r["fleet_scenario"] == fleet_label],
            key=lambda x: x["final_cost_after_2opt_yuan_day"]
        )
        best_run["best_bitmask_after_16_combo_2opt_audit"] = int(best_audit["bitmask"])
        best_run["best_cost_after_16_combo_2opt_audit_yuan_day"] = float(best_audit["cost"])

    # Conditional one-center opening-cost thresholds are reported for the main 8F/25N case.
    if "8F_25N" in selected_fleets:
        best_info = best_perm_by_fleet["8F_25N"]
        no_bits = np.zeros(4, dtype=np.int8)
        no_open_result = decode_fleet(best_info["perm"], no_bits, "S3", stores, demand, nodes,
                                      node_index, matrices, selected_fleets["8F_25N"], policy=True)
        no_open_routes, _ = two_opt_all(no_open_result["routes"], True, matrices, node_index)
        no_open_df, _ = route_cost_table(no_open_routes, True, matrices, node_index, "S3", "8F_25N", "NO_OPEN")
        no_open_cost = float(no_open_df.route_total_cost_yuan.sum())
        candidates = nodes.loc[nodes.node_type.eq("candidate_center"), "node_id"].astype(str).tolist()
        for i, center in enumerate(candidates):
            bits = np.zeros(len(candidates), dtype=np.int8)
            bits[i] = 1
            rr = decode_fleet(best_info["perm"], bits, "S3", stores, demand, nodes,
                              node_index, matrices, selected_fleets["8F_25N"], policy=True)
            if not rr["feasible"]:
                continue
            r2, _ = two_opt_all(rr["routes"], True, matrices, node_index)
            rdf, _ = route_cost_table(r2, True, matrices, node_index, "S3", "8F_25N", f"{best_info['seed']}_{center}")
            operating = float(rdf.route_total_cost_yuan.sum())
            candidate_sens_rows.append({
                "fleet_scenario": "8F_25N", "seed": best_info["seed"], "bitmask": f"single_{center}",
                "opened_centers": center, "feasible": True,
                "route_operating_cost_yuan_day": operating,
                "candidate_open_cost_yuan_day": CANDIDATE_OPEN_COST_YUAN_DAY,
                "total_cost_yuan_day": operating + CANDIDATE_OPEN_COST_YUAN_DAY,
                "conditional_break_even_open_cost_yuan_day": no_open_cost - operating,
                "note": "条件持平点：固定该GA排列及门店解码结构，仅改变单个候选中心日启用成本；非全局阈值。"
            })

    # Save tabular outputs.
    pd.DataFrame(summary_rows).to_csv(out_dir / "fleet_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(run_rows).to_csv(out_dir / "S3_multiseed_runs.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(baseline_route_rows).to_csv(out_dir / "S1_S2_paired_baseline_routes.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(baseline_assign_rows).to_csv(out_dir / "S1_S2_paired_baseline_assignments.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(s3_route_rows).to_csv(out_dir / "S3_optimized_routes_all_seeds.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(s3_assign_rows).to_csv(out_dir / "S3_optimized_assignments_all_seeds.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(history_rows).to_csv(out_dir / "S3_convergence_history.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(check_rows).to_csv(out_dir / "route_feasibility_checks.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(candidate_sens_rows).to_csv(out_dir / "candidate_center_bitset_and_cost_sensitivity.csv", index=False, encoding="utf-8-sig")

    metadata = {
        "case": "Wuhan urban grocery chain LRP",
        "store_count": len(stores), "node_count": len(nodes),
        "total_daily_demand_t": float(sum(demand.values())),
        "fleet_assumptions": selected_fleets,
        "vehicle_parameters": VEHICLES,
        "center_capacity_t": CENTER_CAPACITY_T,
        "candidate_open_cost_yuan_day": CANDIDATE_OPEN_COST_YUAN_DAY,
        "GA_population": args.population, "GA_generations": args.generations,
        "random_seeds": seeds,
        "S1_S2_method": "One common baseline route plan constructed by fixed polar-angle order and constrained-first greedy insertion under daytime policy feasibility; no GA iterations or 2-opt. Same center assignment, vehicle type, and visit sequence evaluated under unrestricted and restricted matrices.",
        "S3_method": "GA with candidate-center bit chromosome and store permutation; S2 baseline permutation injected as an elite individual; directed 2-opt applied after GA; all 16 candidate-center bitsets conditionally decoded and each receives directed 2-opt before comparison.",
        "fleet_constraint": "Each vehicle can perform at most one route per day; route count by vehicle type cannot exceed the assumed available fleet count.",
        "policy_matrix_note": "The fuel_day and nev_eligible matrices are approximations based on the current road-network restriction processing, not authoritative legal GIS boundaries.",
        "demand_note": "Daily store demands are simulated inputs totaling 144.447 t/day; not enterprise transaction records.",
        "vehicle_data_note": "Fleet counts are explicit case-study assumptions, not observed enterprise fleet inventory.",
        "global_optimality": "All S3 results are heuristic best-found feasible solutions, not proofs of global optimality.",
    }
    with open(out_dir / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Make the result directory self-contained and directly runnable on Windows.
    shutil.copy2(Path(__file__).resolve(), out_dir / Path(__file__).name)
    runnable_input = out_dir / "input"
    runnable_input.mkdir(exist_ok=True)
    for fname in [
        "final_node_coordinates_574.csv", "store_demand_seed20261017.csv",
        "distance_unrestricted_km.csv", "distance_fuel_day_km.csv",
        "distance_nev_eligible_km.csv", "candidate_centers_recomputed.csv",
        "store_cluster_assignments.csv",
    ]:
        src = input_dir / fname
        if src.exists():
            shutil.copy2(src, runnable_input / fname)
    (out_dir / "requirements.txt").write_text(
        "numpy\\npandas\\nopenpyxl\\nmatplotlib\\n", encoding="utf-8"
    )

    # Package a copy of inputs for reproducibility.
    snap = out_dir / "input_snapshot"
    snap.mkdir(exist_ok=True)
    for fname in [
        "final_node_coordinates_574.csv", "store_demand_seed20261017.csv",
        "distance_unrestricted_km.csv", "distance_fuel_day_km.csv",
        "distance_nev_eligible_km.csv", "candidate_centers_recomputed.csv",
        "store_cluster_assignments.csv",
    ]:
        src = input_dir / fname
        if src.exists():
            shutil.copy2(src, snap / fname)

    # Excel workbook for inspection.
    xlsx_path = out_dir / "mixed_fleet_three_scenario_results.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="三情景车队敏感性", index=False)
        pd.DataFrame(run_rows).to_excel(writer, sheet_name="S3多随机种子", index=False)
        pd.DataFrame(check_rows).to_excel(writer, sheet_name="约束核验", index=False)
        pd.DataFrame(candidate_sens_rows).to_excel(writer, sheet_name="候选中心敏感性", index=False)
        reach_df.to_excel(writer, sheet_name="车型可达性", index=False)

    # README and reproducibility batch file.
    readme = f"""武汉LRP三情景混合车队重算包

一、基准车队假设
主算例：燃油货车8辆、新能源货车25辆。
敏感性：5辆燃油车+28辆新能源车；12辆燃油车+21辆新能源车。
这些数量是算例假设，不是企业真实车队调查结果。

二、三种情景
S1：无限行道路矩阵；D1、D2固定；使用共同基准线路，不做GA或2-opt。
S2：日间限行道路矩阵；D1、D2固定；与S1完全相同的中心分配、车型及门店访问顺序。
S3：日间限行；D1、D2保留，C1-C4允许自主启用；遗传算法联合搜索中心启用、门店分配、车型和访问顺序，之后进行有向2-opt；对最佳GA排列下的16种候选中心启用位串分别解码并执行有向2-opt后再比较。

三、S1/S2基准线路构造说明
企业历史线路和车辆清单未提供，因此不能将S1/S2称为企业真实历史运营方案。
基准线路采用门店坐标极角排序，并按车型可达性优先级进行容量约束贪心构造。
该过程只生成一套固定可行基准线路，不进行遗传算法迭代或路径局部搜索。
为保证S2可行，基准线路在日间限行矩阵下构造；S1再将完全相同的路线结构代入无限行矩阵进行配对评价。
因此S1/S2差额识别的是同一路线结构下道路矩阵变化的直接影响。

四、车辆约束
每辆车每天最多执行一条配送路线；各车型路线数不得超过假设的可调度车辆数。
燃油货车：载重5.0t，固定成本280元/次，单位里程成本1.28元/km。
新能源货车：载重4.5t，固定成本230元/次，单位里程成本0.30元/km，单路径里程不超过300km。
如企业实际车辆可一天多趟配送，后续需要补充车辆调度/工时约束。

五、运行
1. 安装依赖：pip install numpy pandas openpyxl matplotlib
2. 将input文件夹放在脚本同级目录。
3. 双击run_all_mixed_fleet.bat，或执行：
   python solve_lrp_mixed_fleet_three_scenarios.py --input-dir input --output-dir results

六、解释边界
需求总量144.447t/日为模拟值；车辆数为假设值；限行矩阵为当前道路数据处理近似结果。
S3为启发式最优可行解，不是全局最优证明。
候选中心未启用不表示模型没有选址决策，而是当前1000元/日设施启用成本下，算法选择保留现有中心。
"""
    (out_dir / "README_运行与论文使用说明.txt").write_text(readme, encoding="utf-8")
    bat = """@echo off
chcp 65001 >nul
cd /d %~dp0
python solve_lrp_mixed_fleet_three_scenarios.py --input-dir input --output-dir results
echo.
echo Calculation finished. Check the results folder.
pause
"""
    (out_dir / "run_all_mixed_fleet.bat").write_text(bat, encoding="utf-8-sig")

    # Result package.
    zip_path = out_dir / "武汉LRP三情景混合车队重算结果包.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_dir.rglob("*"):
            if p.is_file() and p.resolve() != zip_path.resolve():
                z.write(p, arcname=str(p.relative_to(out_dir)))
    log("Saved mixed-fleet three-scenario results to", out_dir)
    log("Result package:", zip_path)

if __name__ == "__main__":
    main()
