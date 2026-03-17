import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. 核心配置与时区设定
# ==========================================
DB_FILE = 'classroom_v2.db' 
ROWS = 9     
COLS = 10    
VIP_ROWS = 3 
TEACHER_PWD = "hfyadmin" 
CLASSES = ["25历史学1班", "25历史学2班", "25音乐学2班", "其他"]
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seats
                 (row INTEGER, col INTEGER, student_id TEXT, student_name TEXT, class_name TEXT, timestamp TEXT, PRIMARY KEY(row, col))''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (timestamp TEXT, student_id TEXT, student_name TEXT, class_name TEXT, action TEXT, points INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('class_open', 'True')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_pin', '8888')")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. 数据库读写逻辑
# ==========================================
def get_setting(key):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,)); res = c.fetchone()
    conn.close(); return res[0] if res else None

def update_setting(key, value):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key)); conn.commit(); conn.close()

def clear_all_data():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM seats"); c.execute("DELETE FROM logs"); conn.commit(); conn.close()

def take_seat(row, col, stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    points = 2 if row <= VIP_ROWS else 1
    action = f"入座 {row}排{col}座" if row > VIP_ROWS else f"抢占VIP {row}排{col}座"
    try:
        c.execute("INSERT INTO seats VALUES (?, ?, ?, ?, ?, ?)", (row, col, stu_id, stu_name, class_name, time_str))
        c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, class_name, action, points))
        conn.commit(); conn.close(); return True, points
    except sqlite3.IntegrityError:
        conn.close(); return False, 0

def add_bonus_points(stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, class_name, "课堂主动答题", 2))
    conn.commit(); conn.close()

# ==========================================
# 3. 界面逻辑分发
# ==========================================
st.set_page_config(layout="wide", page_title="课堂互动系统")
view_mode = st.query_params.get("view", "student")
current_pin = get_setting('current_pin')
is_open = get_setting('class_open') == 'True'

if view_mode == "screen":
    # ------------------ 大屏端 (实时热力图) ------------------
    st_autorefresh(interval=3000, limit=None, key="screen_refresh")
    col_main, col_side = st.columns([3, 1.2])
    with col_main:
        st.markdown("<h1 style='text-align: center;'>🎯 《学生心理与教育》课堂实时看板</h1>", unsafe_allow_html=True)
        if is_open: st.markdown(f"<h3 style='text-align: center; color: #D32F2F;'>今日签到口令：【 {current_pin} 】</h3>", unsafe_allow_html=True)
        else: st.markdown("<h3 style='text-align: center; color: gray;'>🚫 签到通道已关闭</h3>", unsafe_allow_html=True)
        st.markdown("---")
        conn = sqlite3.connect(DB_FILE); seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        logs_df = pd.read_sql_query("SELECT student_id, SUM(points) as bonus_pts FROM logs WHERE action LIKE '%答题%' GROUP BY student_id", conn); conn.close()
        bonus_dict = dict(zip(logs_df['student_id'], logs_df['bonus_pts']))
        taken_seats = {(row['row'], row['col']): row for _, row in seats_df.iterrows()}
        for r in range(1, ROWS + 1):
            cols_layout = st.columns([1, 1, 0.4, 1, 1, 1, 1, 1, 1, 0.4, 1, 1])
            seat_col_indices = [0, 1, 3, 4, 5, 6, 7, 8, 10, 11]
            for c in range(1, COLS + 1):
                ui_idx = seat_col_indices[c-1]
                if (r, c) in taken_seats:
                    s = taken_seats[(r, c)]; b = bonus_dict.get(s['student_id'], 0); total = (2 if r <= VIP_ROWS else 1) + b
                    bg = "#D81B60" if b >= 4 else ("#FF9800" if b > 0 else ("#FBC02D" if r <= VIP_ROWS else "#4CAF50"))
                    txt = f"{'🔥' if b>=4 else '🌟' if b>0 else '🧑‍🎓'} {s['student_name']}<br>({total}分)"
                else:
                    bg = "#FFF59D" if r <= VIP_ROWS else "#E0E0E0"
                    txt = f"⭐ {r}-{c}" if r <= VIP_ROWS else f"{r}-{c}"
                cols_layout[ui_idx].markdown(f'<div style="background-color: {bg}; padding: 8px 2px; border-radius: 5px; text-align: center; margin-bottom: 8px; font-weight: bold; color: #333; font-size: 13px;">{txt}</div>', unsafe_allow_html=True)
    with col_side:
        st.header("🏆 排行榜单")
        conn = sqlite3.connect(DB_FILE); lb_df = pd.read_sql_query("SELECT student_name, SUM(points) as total_pts FROM logs GROUP BY student_name ORDER BY total_pts DESC LIMIT 5", conn); conn.close()
        if not lb_df.empty:
            for i, row in lb_df.iterrows():
                rank = i+1; color = ["#D32F2F", "#E64A19", "#F57C00", "#388E3C", "#388E3C"][min(i, 4)]
                st.markdown(f"<div style='background-color: #fff; border: 2px solid {color}; border-radius: 8px; padding: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;'><span style='font-size: 15px; font-weight: bold; color: {color};'>{'👑 榜一' if rank==1 else ('🥈 榜二' if rank==2 else ('🥉 榜三' if rank==3 else f'🏅 第 {rank} 名'))}</span><span style='font-size: 16px; font-weight: bold;'>{row['student_name']} {row['total_pts']}分</span></div>", unsafe_allow_html=True)
        st.markdown("---"); st.subheader("📢 实时动态")
        conn = sqlite3.connect(DB_FILE); l_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 6", conn); conn.close()
        if not l_df.empty:
            for _, r in l_df.iterrows():
                tm = r['timestamp'].split(" ")[1]; ac = r['action']; bc = "#D81B60" if "答题" in ac else ("#FBC02D" if "VIP" in ac else "#1E88E5")
                st.markdown(f"<div style='margin-bottom: 8px; padding: 8px; border-radius: 5px; background-color: #f8f9fa; border-left: 5px solid {bc}; font-size: 12px;'><strong>{'🔥' if '答题' in ac else '⭐' if 'VIP' in ac else '🧑‍🎓'} [{tm}] {r['student_name']}</strong><br>{ac} (+{r['points']})</div>", unsafe_allow_html=True)

elif view_mode == "admin":
    # ------------------ 教师后台 (修正版) ------------------
    st.title("⚙️ 教师管理后台")
    if st.text_input("请输入管理员密码", type="password") == TEACHER_PWD:
        st.success("✅ 身份验证成功")
        
        st.subheader("1. 课堂控制")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 刷新并更换口令", use_container_width=True):
                update_setting('current_pin', str(random.randint(1000, 9999)))
                st.rerun()
        with c2:
            if is_open:
                if st.button("🛑 关闭签到通道", use_container_width=True):
                    update_setting('class_open', 'False'); st.rerun()
            else:
                if st.button("🟢 重新开启签到", use_container_width=True):
                    update_setting('class_open', 'True'); st.rerun()
        
        st.markdown("---")
        st.subheader("2. 数据管理")
        conn = sqlite3.connect(DB_FILE); all_logs = pd.read_sql_query("SELECT * FROM logs", conn)
        c = conn.cursor(); c.execute("SELECT class_name FROM seats ORDER BY timestamp ASC LIMIT 1"); c_name = c.fetchone()
        conn.close(); final_name = f"class_logs_{datetime.datetime.now(BJ_TZ).strftime('%Y%m%d')}_{c_name[0] if c_name else '未签到'}.csv"
        
        st.download_button("📊 导出今日清洗前数据 (CSV)", all_logs.to_csv(index=False).encode('utf-8-sig'), final_name, "text/csv", use_container_width=True)
        
        if st.button("🗑️ 清空今日数据 (下课必点)", type="primary", use_container_width=True):
            clear_all_data(); st.rerun()

else:
    # ------------------ 学生端 (结构化防错版) ------------------
    st.title("🚀 课堂签到互动系统")
    if not is_open: st.error("🛑 老师已关闭通道。"); st.stop()
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        with st.form("login"):
            cn = st.selectbox("选择班级", CLASSES); sid = st.text_input("学号"); sn = st.text_input("姓名"); pin = st.text_input("口令")
            if st.form_submit_button("进入系统", use_container_width=True):
                if pin == current_pin and sid and sn:
                    st.session_state.update({"class_name": cn, "stu_id": sid, "stu_name": sn, "logged_in": True}); st.rerun()
                else: st.error("❌ 信息或口令错误")
    else:
        st_autorefresh(interval=10000, limit=None, key="stu_refresh")
        st.info(f"🧑‍🎓 {st.session_state.stu_name} | {st.session_state.class_name}")
        t1, t2, t3 = st.tabs(["🪑 抢占座位", "🙋 答题加分", "🏆 排行榜"])
        with t1:
            conn = sqlite3.connect(DB_FILE); s_df = pd.read_sql_query("SELECT * FROM seats", conn); conn.close()
            my = s_df[s_df['student_id'] == st.session_state.stu_id]
            if not my.empty: st.success(f"✅ 已入座：{my.iloc[0]['row']}排-{my.iloc[0]['col']}座")
            else:
                tk = set(zip(s_df['row'], s_df['col'])); av = [None]
                for r in range(1, ROWS + 1):
                    for c in range(1, COLS + 1):
                        if (r, c) not in tk: av.append((r, c, "⭐VIP" if r<=VIP_ROWS else "🪑普通"))
                with st.form("seat"):
                    sel = st.selectbox("请准确点选座位：", av, format_func=lambda x: f"{x[2]} {x[0]}排-{x[1]}座" if x else "-- 点击下拉选择 --")
                    if st.form_submit_button("确认提交", type="primary"):
                        if sel:
                            ok, p = take_seat(sel[0], sel[1], st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                            if ok: st.success(f"成功获得 {p} 分！"); st.rerun()
                            else: st.error("被抢了，请刷新重试！")
                        else: st.warning("未选择座位")
        with t2:
            if st.button("🙋 我刚回答了提问 (加2分)", use_container_width=True):
                add_bonus_points(st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name); st.success("加分上墙！")
        with t3:
            conn = sqlite3.connect(DB_FILE); lb = pd.read_sql_query("SELECT student_name, SUM(points) as total FROM logs GROUP BY student_name ORDER BY total DESC LIMIT 10", conn); conn.close()
            for i, r in lb.iterrows(): st.markdown(f"**{i+1}. {r['student_name']}** ({r['total']}分)")
