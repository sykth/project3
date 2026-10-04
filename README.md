# 🎯 포트리스 2D 투사체 운동 시뮬레이터

중력 · 공기저항 · 바람 속에서 포탄이 어떻게 날아가는지를 **오일러 방법(Euler method)** 으로 한 걸음씩 계산해서 보여주는 시뮬레이터예요.
포트리스 같은 게임 화면으로 쏴 보면서, 시간 간격 **h** 가 계산 오차에 어떤 영향을 주는지 직접 실험할 수 있어요.

> 🔗 **데모**: (배포 후 여기에 Streamlit 주소를 붙여 넣기)

## 무엇을 볼 수 있나요?

| 화면 | 설명 |
| --- | --- |
| 전장 (왼쪽, 5) | 지형 + 탱크 2대. 각도·파워·바람을 정하고 발사하면 흰 점으로 궤적이 찍혀요. |
| 터미널 (오른쪽, 2) | 오일러 방법이 한 걸음씩 계산되는 값(`n, t, x, y, v`)이 실시간으로 나와요. |
| 📖 자세히 설명 | 계산에 쓰인 방정식을 LaTeX 수식으로 쉽게 풀어 쓴 문서 (`docs/equations.md`) |
| 📈 h별 오차 분석 | h 를 바꿨을 때 착탄 오차를 로그-로그 그래프로 그려요. 기울기 ≈ 1 → 오차가 h 에 비례! |

**궤적 3종류 비교**

- ⚪ 오일러 (게임이 실제로 쓰는 계산)
- 🟡 RK4, h = 0.002 s (거의 정답인 기준)
- 🔵 진공 해석해 (공기저항·바람이 없을 때의 정확한 공식)

## 물리 모델

$$
\frac{dx}{dt}=v_x,\quad \frac{dy}{dt}=v_y,\quad
\frac{dv_x}{dt}=-c\,|v_{rel}|\,(v_x-w),\quad
\frac{dv_y}{dt}=-g-c\,|v_{rel}|\,v_y
$$

$$
|v_{rel}|=\sqrt{(v_x-w)^2+v_y^2},\qquad g=9.8\ \mathrm{m/s^2},\quad c=0.0025\ \mathrm{1/m}
$$

오일러 방법: $\;x_{n+1}=x_n+v_{x,n}\,h,\;\; v_{x,n+1}=v_{x,n}+a_x\,h$ (y 방향도 같은 방식)

자세한 풀이는 [`docs/equations.md`](docs/equations.md) 에 있어요.

## 폴더 구조

```
fortress-sim/
├─ app.py                  # Streamlit 웹 앱 (진입점)
├─ sim_core.py             # 계산 엔진 (순수 파이썬, 웹/데스크톱/테스트 공용)
├─ docs/
│  └─ equations.md         # '자세히 설명' 버튼에 뜨는 방정식 문서
├─ tests/
│  └─ test_sim_core.py     # 계산 엔진 검증 (오차 차수 등)
├─ desktop/
│  ├─ fortress_sim.py      # Pygame 데스크톱 버전 (키보드로 즐기는 2인용 게임)
│  └─ requirements.txt
├─ .streamlit/config.toml  # 다크 테마
├─ requirements.txt        # 웹 배포용 패키지
└─ .gitignore
```

## 내 컴퓨터에서 실행

```bash
# 1) 가상환경 (선택이지만 추천)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 설치 & 실행
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 이 열리면 성공!

### 테스트

```bash
python -m unittest discover -s tests -v
```

### 데스크톱(Pygame) 버전

```bash
pip install -r desktop/requirements.txt
python desktop/fortress_sim.py
```

> Pygame 은 컴퓨터 화면에 창을 직접 띄우는 라이브러리라서 웹 서버에서는 실행할 수 없어요.
> 그래서 웹 버전(`app.py`)은 같은 계산 엔진을 Streamlit + Plotly 로 다시 그린 거예요.

## GitHub 에 올리기

1. github.com 에서 **New repository** → 이름 `fortress-sim` (README/.gitignore 는 **추가하지 않기**, 이미 있어요)
2. 이 폴더에서:

```bash
git init
git add .
git commit -m "포트리스 투사체 시뮬레이터 첫 커밋"
git branch -M main
git remote add origin https://github.com/<내 아이디>/fortress-sim.git
git push -u origin main
```

## Streamlit Community Cloud 에 배포 (무료)

1. [share.streamlit.io](https://share.streamlit.io) 에 GitHub 계정으로 로그인
2. **Create app** → 방금 올린 저장소 선택
3. Branch: `main`, Main file path: `app.py`
4. (선택) Advanced settings 에서 Python 3.11 또는 3.12 선택
5. **Deploy** → 몇 분 뒤 `https://<앱이름>.streamlit.app` 주소가 생겨요. 그 주소를 위쪽 **데모** 줄에 붙여 넣으세요.

저장소에 push 할 때마다 웹사이트도 자동으로 업데이트돼요.

## 계산 엔진만 따로 쓰기

```python
import sim_core as sc

field = sc.Field(seed=7)
s0 = field.launch(shooter=0, angle_deg=45, power=70)
pts, hit = field.simulate(sc.euler_step, 0.05, s0, shooter=0, wind=3.0)
print(hit)   # (착탄 x, y, 시간, ('ground', None))
```

## 더 해 볼 만한 것

- RK4 의 h 를 키워도 오일러 h = 0.01 보다 정확한지 비교하기
- 공기저항이 있을 때 사거리가 최대인 각도 찾기 (45° 보다 클까, 작을까?)
- 오차 분석 그래프에 RK4 의 기울기(≈ 4)도 같이 그리기
