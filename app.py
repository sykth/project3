# -*- coding: utf-8 -*-
"""
포트리스 2D 투사체 운동 시뮬레이터 — Streamlit 웹 버전

  실행 :  streamlit run app.py

화면 구성 (5 : 2)
  - 왼쪽(5)  : 전장(지형 + 탱크 2대 + 궤적)
  - 오른쪽(2): 터미널 — 오일러 방법이 한 걸음씩 계산되는 모습을 실시간 출력
              + [자세히 설명] 버튼 → 방정식 문서(LaTeX 수식)
  - 아래     : h 를 바꿨을 때 오차가 어떻게 변하는지 로그-로그 그래프
"""
import html
import math
import time
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

import sim_core as sc

st.set_page_config(page_title="포트리스 투사체 시뮬레이터", page_icon="🎯", layout="wide")

EQ_PATH = Path(__file__).parent / "docs" / "equations.md"
TERM_COLORS = {"cmd": "#78e18c", "info": "#7dbeff", "step": "#8ca591",
               "warn": "#ffcd5a", "err": "#ff7373", "dim": "#697870"}
PLAYER_COLORS = ["#50a0ff", "#ff6e5a"]
PLOT_CONFIG = {"displayModeBar": False}


# ═════════════════════ 설명 문서 (자세히 설명 버튼) ═════════════════════
def load_equations():
    try:
        return EQ_PATH.read_text(encoding="utf-8")
    except OSError:
        return "설명 파일(docs/equations.md)을 찾을 수 없어요."


@st.dialog("계산에 쓰인 방정식", width="large")
def show_equations():
    st.markdown(load_equations())


# ═════════════════════ 터미널 (HTML) ═════════════════════
def term_html(lines, rows=34, height=540):
    body = []
    for text, kind in lines[-rows:]:
        color = TERM_COLORS.get(kind, "#8ca591")
        body.append('<div style="color:%s">%s</div>' % (color, html.escape(text) if text else "&nbsp;"))
    bar = ('<div style="background:#20242c;padding:8px 12px;display:flex;align-items:center;gap:7px;">'
           '<span style="width:12px;height:12px;border-radius:50%;background:#ff5f56;display:inline-block"></span>'
           '<span style="width:12px;height:12px;border-radius:50%;background:#ffbd2e;display:inline-block"></span>'
           '<span style="width:12px;height:12px;border-radius:50%;background:#27c93f;display:inline-block"></span>'
           '<span style="color:#bec3cd;margin-left:8px;font-size:12px">trajectory-solver -- bash</span></div>')
    return ('<div style="background:#0c0e12;border:1px solid #3a4152;border-radius:10px;overflow:hidden;'
            'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,\'D2Coding\',monospace;'
            'font-size:12px;line-height:1.4;">%s'
            '<div style="padding:8px 12px;height:%dpx;overflow:hidden;white-space:pre;display:flex;'
            'flex-direction:column;justify-content:flex-end;">%s</div></div>'
            % (bar, height, "".join(body)))


def intro_lines():
    return [("trajectory-solver v1.0", "info"),
            ("explicit Euler + RK4 reference", "dim"),
            ("", "dim"),
            ("left panel: set angle/power,", "dim"),
            ("then press FIRE in the sidebar", "dim"),
            ("$ _", "cmd")]


# ═════════════════════ 전장 그림 ═════════════════════
def make_fig(field, shooter, angle, euler_pts=None, ghost=None, proj=None, impact=None):
    """ghost = (ref_pts, vac_pts) 또는 None"""
    fig = go.Figure()

    # 지형
    idx = list(range(0, sc.GAME_W_PX, 2))
    fig.add_trace(go.Scatter(
        x=[i / sc.PX_PER_M for i in idx], y=[field.ground[i] for i in idx],
        mode="lines", fill="tozeroy", fillcolor="#70502f",
        line=dict(color="#50af58", width=3), hoverinfo="skip", showlegend=False))

    # 탱크 (몸통 + 포신)
    for i in (0, 1):
        tx, gy = field.tank_pos(i)
        d = field.facing(i)
        th = math.radians(angle if i == shooter else 45.0)
        px_, py_ = tx, gy + sc.PIVOT_H
        col = PLAYER_COLORS[i]
        fig.add_trace(go.Scatter(
            x=[px_, px_ + d * math.cos(th) * sc.BARREL_L], y=[py_, py_ + math.sin(th) * sc.BARREL_L],
            mode="lines", line=dict(color="#23232a", width=6), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[tx - 3.8, tx + 3.8, tx + 3.8, tx - 3.8, tx - 3.8], y=[gy, gy, gy + 2.2, gy + 2.2, gy],
            mode="lines", fill="toself", fillcolor=col, line=dict(color=col, width=1),
            hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[px_], y=[py_], mode="markers+text", text=["P%d" % (i + 1)], textposition="top center",
            textfont=dict(color=col, size=13), marker=dict(color=col, size=13),
            hoverinfo="skip", showlegend=False))

    # 비교 궤적 (착탄 후에만)
    if ghost is not None:
        ref_pts, vac_pts = ghost
        if vac_pts:
            fig.add_trace(go.Scatter(
                x=[p[0] for p in vac_pts], y=[p[1] for p in vac_pts], mode="markers", name="진공 해석해",
                marker=dict(color="#5aebeb", size=4), hovertemplate="x=%{x:.1f} m<br>y=%{y:.1f} m<extra>진공</extra>"))
        if ref_pts:
            fig.add_trace(go.Scatter(
                x=[p[0] for p in ref_pts], y=[p[1] for p in ref_pts], mode="markers", name="RK4 (기준)",
                marker=dict(color="#ffe150", size=4), hovertemplate="x=%{x:.1f} m<br>y=%{y:.1f} m<extra>RK4</extra>"))

    # 오일러 궤적
    if euler_pts and len(euler_pts) > 1:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in euler_pts], y=[p[1] for p in euler_pts], mode="lines+markers", name="오일러 (게임)",
            line=dict(color="rgba(235,235,245,0.7)", width=1), marker=dict(color="#ffffff", size=6),
            hovertemplate="x=%{x:.1f} m<br>y=%{y:.1f} m<extra>오일러</extra>"))

    if proj is not None:
        fig.add_trace(go.Scatter(x=[proj[0]], y=[proj[1]], mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(color="#ff5a3c", size=14, line=dict(color="#ffe6c8", width=2))))
    if impact is not None:
        fig.add_trace(go.Scatter(x=[impact[0]], y=[impact[1]], mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(symbol="star", color="#ffb432", size=24,
                                             line=dict(color="#fff0aa", width=2))))

    fig.update_layout(
        height=540, margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#9ec5ee", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, sc.FIELD_W], showgrid=False, zeroline=False, showticklabels=False,
                   fixedrange=True, constrain="domain"),
        yaxis=dict(range=[0, sc.FIELD_H], showgrid=False, zeroline=False, showticklabels=False,
                   fixedrange=True, scaleanchor="x", scaleratio=1, constrain="domain"),
        legend=dict(orientation="h", x=0.01, y=0.99, bgcolor="rgba(10,14,24,0.55)", font=dict(color="#ffffff")),
        hovermode="closest",
    )
    return fig


def verdict_text(hit, field, shooter):
    """착탄 결과를 한 줄로 설명 -> (종류, 문장)"""
    if hit is None:
        return "warning", "시간 초과로 끝났어요."
    kind, who = hit[3]
    other = 1 - shooter
    ox, oy = field.tank_pos(other)
    dist = math.hypot(hit[0] - ox, hit[1] - (oy + sc.TANK_HIT_Y))
    if kind == "tank" and who == other:
        return "success", "명중! P%d 를 맞췄어요 🎯" % (other + 1)
    if kind == "tank":
        return "error", "자기 탱크를 맞췄어요 😅"
    if kind == "out":
        return "warning", "필드 밖으로 날아갔어요."
    return "info", "땅에 떨어졌어요 (x = %.1f m). P%d 까지 %.1f m 남았어요." % (hit[0], other + 1, dist)


# ═════════════════════ 발사 (실시간 계산) ═════════════════════
def play_shot(field, shooter, angle, power, wind, h, animate, plot_ph, term_ph, msg_ph):
    s0 = field.launch(shooter, angle, power)
    ref_pts, ref_hit = field.simulate(sc.rk4_step, sc.REF_H, s0, shooter, wind)
    vac_pts, vac_hit = field.simulate_vacuum(s0, shooter)

    lines = sc.header_lines("P%d" % (shooter + 1), angle, power, s0, wind, h)
    pts = [(s0[1], s0[2])]
    s, n, hit = s0, 0, None
    ui_every = max(1, round(0.1 / h))           # 시뮬레이션 0.1초마다 화면 갱신

    while True:
        s1 = sc.euler_step(s, h, wind)
        n += 1
        if n == 1:
            lines += sc.detail_lines(s, s1, wind)
        lines.append((sc.step_line(n, s1), "step"))
        hit = field.seg_hit(s, s1, shooter)
        if hit:
            pts.append((hit[0], hit[1]))
            break
        s = s1
        pts.append((s[1], s[2]))
        if s[0] >= sc.T_MAX:
            break
        if animate and n % ui_every == 0:
            term_ph.markdown(term_html(lines), unsafe_allow_html=True)
            plot_ph.plotly_chart(make_fig(field, shooter, angle, euler_pts=pts, proj=pts[-1]),
                                 config=PLOT_CONFIG)
            time.sleep(0.03)

    if hit and hit[3][0] != "out":
        lines.append(("IMPACT at x=%.2f y=%.2f t=%.2f" % (hit[0], hit[1], hit[2]), "err"))
    else:
        lines.append(("MISS", "err"))
    lines += sc.result_lines(h, hit, ref_hit, vac_hit)
    lines.append(("$ _", "cmd"))

    st.session_state["last"] = dict(
        seed=field.seed, shooter=shooter, h=h, pts=pts, ref_pts=ref_pts, vac_pts=vac_pts,
        hit=hit, lines=lines)
    render_last(field, shooter, angle, plot_ph, term_ph, msg_ph, show_cmp=True)


def render_last(field, shooter, angle, plot_ph, term_ph, msg_ph, show_cmp):
    last = st.session_state.get("last")
    if last and last["seed"] == field.seed:
        ghost = (last["ref_pts"], last["vac_pts"]) if show_cmp else None
        impact = (last["hit"][0], last["hit"][1]) if last["hit"] and last["hit"][3][0] != "out" else None
        plot_ph.plotly_chart(
            make_fig(field, shooter, angle, euler_pts=last["pts"], ghost=ghost, impact=impact),
            config=PLOT_CONFIG)
        term_ph.markdown(term_html(last["lines"]), unsafe_allow_html=True)
        kind, text = verdict_text(last["hit"], field, last["shooter"])
        getattr(msg_ph, kind)(text)
    else:
        plot_ph.plotly_chart(make_fig(field, shooter, angle), config=PLOT_CONFIG)
        term_ph.markdown(term_html(intro_lines()), unsafe_allow_html=True)
        msg_ph.empty()


# ═════════════════════ 오차 분석 (캐시) ═════════════════════
@st.cache_data(show_spinner=False)
def cached_error_study(seed, shooter, angle, power, wind):
    ref, rows = sc.error_study(sc.Field(seed), shooter, angle, power, wind)
    return ref, rows, sc.loglog_slope(rows)


def error_figure(rows):
    rows = [r for r in rows if abs(r[2]) > 1e-9]            # 로그 축에는 0 을 그릴 수 없음
    hs = [r[0] for r in rows]
    es = [abs(r[2]) for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hs, y=es, mode="lines+markers", name="오일러 오차 |Δx|",
                             marker=dict(size=9, color="#ffe150"), line=dict(color="#ffe150", width=2)))
    ref_line = [es[0] * (h / hs[0]) for h in hs]            # 기울기 1 기준선
    fig.add_trace(go.Scatter(x=hs, y=ref_line, mode="lines", name="기울기 1 (오차 ∝ h)",
                             line=dict(color="#8ca0b4", width=2, dash="dash")))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(type="log", title="시간 간격 h (초)"),
                      yaxis=dict(type="log", title="착탄 오차 |Δx| (m)"),
                      legend=dict(orientation="h", y=1.1))
    return fig


# ═════════════════════ 화면 구성 ═════════════════════
st.title("🎯 포트리스 투사체 운동 시뮬레이터")
st.caption("중력 · 공기저항 · 바람 속 포탄의 운동을 **오일러 방법**으로 한 걸음씩 계산해 봐요. "
           "왼쪽 사이드바에서 값을 정하고 발사!")

with st.sidebar:
    st.header("조종석")
    shooter_label = st.radio("쏘는 사람", ["P1 (왼쪽)", "P2 (오른쪽)"], horizontal=True)
    angle = st.slider("각도 (°)", 0, 90, 45)
    power = st.slider("파워", 5, 100, 70)
    wind = st.slider("바람 (m/s)", -sc.WIND_MAX, sc.WIND_MAX, 3.0, 0.5,
                     help="+ 는 오른쪽으로, − 는 왼쪽으로 부는 바람")
    h = st.select_slider("오일러 시간 간격 h (초)", options=sc.H_OPTIONS, value=0.05,
                         help="작을수록 정확하지만 계산이 많아져요")
    seed = int(st.number_input("지형 번호", min_value=0, max_value=9999, value=7, step=1))
    show_cmp = st.toggle("비교 궤적 보기 (RK4 · 진공)", value=True)
    animate = st.toggle("실시간 계산 애니메이션", value=True)
    fire = st.button("🔥 발사!", type="primary")

shooter = 0 if shooter_label.startswith("P1") else 1
field = sc.Field(seed)

left, right = st.columns([5, 2])                         # 화면 5 : 2
with left:
    plot_ph = st.empty()
    msg_ph = st.empty()
with right:
    term_ph = st.empty()
    open_eq = st.button("📖 자세히 설명")

if fire:
    play_shot(field, shooter, angle, power, wind, h, animate, plot_ph, term_ph, msg_ph)
else:
    render_last(field, shooter, angle, plot_ph, term_ph, msg_ph, show_cmp)

if open_eq:
    show_equations()

# ───────── h별 오차 분석 ─────────
st.divider()
st.subheader("📈 h를 줄이면 오차는 얼마나 줄까?")
st.write("지금 사이드바의 각도·파워·바람으로 쐈을 때, 오일러 방법의 착탄 위치가 "
         "기준(RK4)과 얼마나 다른지 h 별로 계산했어요. (평평한 바닥에 떨어진다고 가정)")

ref_x, rows, slope = cached_error_study(seed, shooter, angle, power, wind)
if ref_x is None or len(rows) < 3:
    st.info("이 설정에서는 포탄이 바닥에 닿지 않아서 오차를 계산할 수 없어요. 각도나 파워를 바꿔 보세요.")
else:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(error_figure(rows), config=PLOT_CONFIG)
    with c2:
        st.metric("로그-로그 기울기", "-" if slope is None else "%.2f" % slope,
                  help="1 에 가까우면 '오차가 h 에 비례' 한다는 뜻 (1차 방법)")
        st.metric("기준(RK4) 착탄 거리", "%.2f m" % ref_x)
        st.dataframe(
            [{"h (초)": r[0], "오일러 착탄 x (m)": round(r[1], 3), "오차 (m)": round(r[2], 4)} for r in rows],
            hide_index=True)
    st.caption("기울기가 1 이면 h 를 절반으로 줄일 때 오차도 절반이 돼요. "
               "오일러 방법의 전역 오차가 O(h) 라는 이론을 눈으로 확인하는 그래프예요.")
