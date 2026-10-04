# -*- coding: utf-8 -*-
"""
sim_core.py — 포트리스 투사체 시뮬레이터의 '계산 엔진'

pygame / streamlit 에 의존하지 않는 순수 파이썬 모듈이라서
웹(app.py)에서도, 테스트에서도, 다른 프로그램에서도 그대로 가져다 쓸 수 있다.

상태 s = (t, x, y, vx, vy)   단위: 초, m, m, m/s, m/s   (y 는 위쪽이 +)
"""
import math
import random

# ───────────────────────── 상수 ─────────────────────────
GAME_W_PX = 1000               # 지형 열 개수 (1열 = 1px = 0.2 m)
PX_PER_M = 5.0
FIELD_W = GAME_W_PX / PX_PER_M  # 200 m
FIELD_H = 128.0                # 화면에 보이는 높이 [m]

G = 9.8                        # 중력가속도 [m/s^2]
C_DRAG = 0.0025                # 공기저항 계수 [1/m]
V_PER_POWER = 0.55             # 파워 1당 초기속도 [m/s]
WIND_MAX = 12.0
H_OPTIONS = [0.2, 0.1, 0.05, 0.02, 0.01]
REF_H = 0.002                  # 기준 궤적(RK4) 시간 간격
T_MAX = 60.0

PIVOT_H = 2.2                  # 지면 ~ 포신 축 높이 [m]
BARREL_L = 3.5                 # 포신 길이 [m]
TANK_HIT_Y = 1.5
TANK_HIT_R = 2.8
TANK_X = (26.0, 174.0)         # P1, P2 의 x 위치 [m]


# ───────────────────────── 물리: 오일러 / RK4 ─────────────────────────
def accel(vx, vy, wind):
    """중력 + 공기저항(공기에 대한 상대속도 기준)"""
    rx = vx - wind
    sp = math.hypot(rx, vy)
    return -C_DRAG * sp * rx, -G - C_DRAG * sp * vy


def euler_step(s, h, wind):
    t, x, y, vx, vy = s
    ax, ay = accel(vx, vy, wind)
    return (t + h, x + vx * h, y + vy * h, vx + ax * h, vy + ay * h)


def rk4_step(s, h, wind):
    t, x, y, vx, vy = s

    def f(vx_, vy_):
        ax, ay = accel(vx_, vy_, wind)
        return vx_, vy_, ax, ay

    k1 = f(vx, vy)
    k2 = f(vx + 0.5 * h * k1[2], vy + 0.5 * h * k1[3])
    k3 = f(vx + 0.5 * h * k2[2], vy + 0.5 * h * k2[3])
    k4 = f(vx + h * k3[2], vy + h * k3[3])
    w = h / 6.0
    return (t + h,
            x + w * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
            y + w * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
            vx + w * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
            vy + w * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3]))


# ───────────────────────── 지형 / 필드 ─────────────────────────
def make_terrain(seed):
    rng = random.Random(seed)
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    am = [rng.uniform(8, 14), rng.uniform(4, 8), rng.uniform(2, 4), rng.uniform(1, 2)]
    ground = []
    for i in range(GAME_W_PX):
        u = i / GAME_W_PX * 2 * math.pi
        h = (28 + am[0] * math.sin(u * 1.2 + ph[0]) + am[1] * math.sin(u * 2.7 + ph[1])
             + am[2] * math.sin(u * 6 + ph[2]) + am[3] * math.sin(u * 13 + ph[3]))
        ground.append(max(8.0, h))
    for tx in TANK_X:                                   # 탱크 자리는 평평하게
        c = int(tx * PX_PER_M)
        base = ground[c]
        for i in range(max(0, c - 20), min(GAME_W_PX, c + 21)):
            ground[i] = base
    return ground


class Field:
    """지형 + 두 탱크가 놓인 전장. 충돌 판정과 궤적 계산을 담당한다."""

    def __init__(self, seed):
        self.seed = seed
        self.ground = make_terrain(seed)

    def ground_at(self, x_m):
        i = int(x_m * PX_PER_M)
        return self.ground[min(max(i, 0), GAME_W_PX - 1)]

    def tank_pos(self, idx):
        x = TANK_X[idx]
        return x, self.ground_at(x)

    @staticmethod
    def facing(idx):
        return 1 if idx == 0 else -1

    def launch(self, shooter, angle_deg, power):
        """발사 순간의 상태 s0 (포신 끝에서 출발)"""
        tx, gy = self.tank_pos(shooter)
        d = self.facing(shooter)
        th = math.radians(angle_deg)
        v0 = V_PER_POWER * power
        x0 = tx + d * BARREL_L * math.cos(th)
        y0 = gy + PIVOT_H + BARREL_L * math.sin(th)
        return (0.0, x0, y0, d * v0 * math.cos(th), v0 * math.sin(th))

    # ── 충돌 판정 ──
    def hit_test(self, x, y, t, shooter):
        if x < 0 or x >= FIELD_W:
            return ("out", None)
        if y <= self.ground_at(x):
            return ("ground", None)
        for i in (0, 1):
            if i == shooter and t < 1.0:          # 쏜 직후 자기 탱크는 무시
                continue
            tx, gy = self.tank_pos(i)
            if math.hypot(x - tx, y - (gy + TANK_HIT_Y)) <= TANK_HIT_R:
                return ("tank", i)
        return None

    def seg_hit(self, a, b, shooter):
        """a -> b 선분을 1px 간격으로 검사 (큰 h 에서 벽/탱크를 건너뛰는 '터널링' 방지)"""
        dxm, dym = b[1] - a[1], b[2] - a[2]
        n = max(1, int(math.hypot(dxm, dym) * PX_PER_M))
        for k in range(1, n + 1):
            f = k / n
            x, y, t = a[1] + dxm * f, a[2] + dym * f, a[0] + (b[0] - a[0]) * f
            r = self.hit_test(x, y, t, shooter)
            if r:
                return (x, y, t, r)
        return None

    # ── 궤적 계산 ──
    def simulate(self, stepper, h, s0, shooter, wind, dot_every_s=0.03):
        """착탄할 때까지 계산. -> (점 목록, 충돌 정보 or None)"""
        s = s0
        pts = [(s[1], s[2])]
        every = max(1, int(round(dot_every_s / h)))
        n = 0
        while s[0] < T_MAX:
            s2 = stepper(s, h, wind)
            n += 1
            hit = self.seg_hit(s, s2, shooter)
            if hit:
                pts.append((hit[0], hit[1]))
                return pts, hit
            s = s2
            if n % every == 0:
                pts.append((s[1], s[2]))
        return pts, None

    def simulate_vacuum(self, s0, shooter):
        """공기저항·바람이 없을 때의 해석해(정확한 공식) 궤적"""
        _, x0, y0, vx, vy = s0
        pts = [(x0, y0)]
        dt, k = 0.01, 0
        prev = s0
        while k * dt < T_MAX:
            k += 1
            t = k * dt
            cur = (t, x0 + vx * t, y0 + vy * t - 0.5 * G * t * t, vx, vy - G * t)
            hit = self.seg_hit(prev, cur, shooter)
            if hit:
                pts.append((hit[0], hit[1]))
                return pts, hit
            prev = cur
            if k % 3 == 0:
                pts.append((cur[1], cur[2]))
        return pts, None


# ───────────────────────── 오차 분석 (평지 착탄) ─────────────────────────
def landing_flat(stepper, h, s0, wind, y_plane):
    """y = y_plane 인 평평한 바닥에 닿는 x 좌표. 마지막 두 점 사이를 직선 보간해서
    '충돌 판정의 픽셀 해상도' 때문에 생기는 잡음 없이 순수한 수치 오차만 잰다."""
    s = s0
    while s[0] < T_MAX:
        s2 = stepper(s, h, wind)
        if s[2] > y_plane >= s2[2]:
            f = (s[2] - y_plane) / (s[2] - s2[2])
            return s[1] + (s2[1] - s[1]) * f
        s = s2
    return None


ERROR_HS = [0.2, 0.1, 0.05, 0.02, 0.01, 0.005]


def error_study(field, shooter, angle_deg, power, wind, hs=ERROR_HS):
    """h 를 바꿔 가며 오일러 착탄점이 RK4(기준)와 얼마나 다른지 계산.
    반환: (기준 x, [(h, 오일러 x, 부호 있는 오차 [m]), ...])  — 오차 > 0 이면 오일러가 더 멀리 날아감"""
    s0 = field.launch(shooter, angle_deg, power)
    y_plane = field.tank_pos(shooter)[1]
    d = field.facing(shooter)
    ref = landing_flat(rk4_step, REF_H, s0, wind, y_plane)
    rows = []
    if ref is None:
        return None, rows
    for h in hs:
        x = landing_flat(euler_step, h, s0, wind, y_plane)
        if x is not None:
            rows.append((h, x, (x - ref) * d))
    return ref, rows


def loglog_slope(rows):
    """log|오차| - log h 직선의 기울기 (최소제곱). 점이 3개 미만이면 None"""
    pts = [(math.log10(h), math.log10(abs(e))) for h, _, e in rows if abs(e) > 1e-9]
    if len(pts) < 3:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den == 0:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in pts) / den


# ───────────────────────── 터미널 출력용 문자열 ─────────────────────────
# 각 줄은 (텍스트, 종류) — 종류: cmd / info / step / warn / err / dim
def step_line(n, s):
    return "n=%03d t=%5.2f x=%6.1f y=%5.1f v=(%6.1f,%6.1f)" % (n, s[0], s[1], s[2], s[3], s[4])


def header_lines(name, angle, power, s0, wind, h):
    v0 = V_PER_POWER * power
    return [
        ("", "dim"),
        ("$ fire --%s --angle %.1f --power %.1f" % (name, angle, power), "cmd"),
        ("v0  = %.2f * %.1f = %.2f m/s" % (V_PER_POWER, power, v0), "info"),
        ("vx0 = %+.3f   vy0 = %+.3f" % (s0[3], s0[4]), "info"),
        ("x0=%.2f y0=%.2f  w=%+.1f" % (s0[1], s0[2], wind), "info"),
        ("c=%g  g=%g  h=%g s" % (C_DRAG, G, h), "info"),
        ("-- explicit Euler --", "warn"),
    ]


def detail_lines(s0, s1, wind):
    _, _, _, vx, vy = s0
    ax, ay = accel(vx, vy, wind)
    vrel = math.hypot(vx - wind, vy)
    return [
        ("[step 1 in detail]", "warn"),
        (" |v_rel| = %.3f" % vrel, "info"),
        (" ax = -c|v_rel|(vx-w) = %+.3f" % ax, "info"),
        (" ay = -g-c|v_rel|vy   = %+.3f" % ay, "info"),
        (" x1  = x0 + vx0*h = %.3f" % s1[1], "info"),
        (" y1  = y0 + vy0*h = %.3f" % s1[2], "info"),
        (" vx1 = vx0 + ax*h = %+.3f" % s1[3], "info"),
        (" vy1 = vy0 + ay*h = %+.3f" % s1[4], "info"),
        ("[...]", "warn"),
    ]


def land_x(hit):
    if hit is None or hit[3][0] == "out":
        return None
    return hit[0]


def fmt_land(hit):
    if hit is None:
        return "no landing"
    if hit[3][0] == "out":
        return "out of field"
    return "x=%7.2f m" % hit[0]


def result_lines(h, hit, ref_hit, vac_hit):
    ref, eul, vac = land_x(ref_hit), land_x(hit), land_x(vac_hit)
    out = [("== RESULT ==", "warn"),
           ("euler h=%-5g %s" % (h, fmt_land(hit)), "step"),
           ("rk4   h=%-5g %s" % (REF_H, fmt_land(ref_hit)), "step")]
    if eul is not None and ref is not None:
        out.append(("dx(euler-rk4) = %+.3f m" % (eul - ref), "warn"))
    out.append(("vacuum (no drag/wind) %s" % fmt_land(vac_hit), "step"))
    if ref is not None and vac is not None:
        out.append(("drag+wind shift = %+.2f m" % (ref - vac), "warn"))
    return out
