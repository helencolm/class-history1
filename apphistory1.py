import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. 核心配置与数据库初始化
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def update_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()
    conn.close()

def generate_new_pin():
    new_pin = str(random.randint(1000, 9999))
    update_setting('current_pin', new_pin)
    return new_pin

def clear_all_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM seats")
    c.execute("DELETE FROM logs")
    conn.commit()
    conn.close()

def take_seat(row, col, stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT student_id FROM seats WHERE row=? AND col=?", (row, col))
    if c.fetchone() is None:
        time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO seats VALUES (?, ?, ?, ?, ?, ?)", 
                  (row, col, stu_id, stu_name, class_name, time_str))
        
        points = 2 if row <= VIP_ROWS else 1
        action = f"入座 {row}排{col}座" if row > VIP_ROWS else f"抢占VIP {row}排{col}座"
        c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", 
                  (time_str, stu_id, stu_name, class_name, action, points))
        conn.commit()
        conn.close()
        return True, points
    conn.close()
    return False, 0

def add_bonus_points(stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", 
              (time_str, stu_id, stu_name, class_name, "课堂主动答题", 2))
    conn.commit()
    conn.close()

# ==========================================
# 3. 界面渲染路由
# ==========================================
st.set_page_config(layout="wide", page_title="课堂签到加分系统")
query_params = st.query_params
view_mode = query_params.get("view", "student")

current_pin = get_setting('current_pin')
is_open = get_setting('class_open') == 'True'

if view_mode == "screen":
    # ------------------ 大屏端 ------------------
    st_autorefresh(interval=3000, limit=None, key="screen_refresh")
    
    col_main, col_side = st.columns([3, 1.2])
    
    with col_main:
        st.markdown("<h1 style='text-align: center;'>🎯 《学生心理与教育》课堂座位实时热力图</h1>", unsafe_allow_html=True)
        if is_open:
            st.markdown(f"<h3 style='text-align: center; color: #D32F2F;'>今日签到口令：【 {current_pin} 】</h3>", unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='text-align: center; color: gray;'>🚫 签到通道已关闭</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        conn = sqlite3.connect(DB_FILE)
        seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        logs_df = pd.read_sql_query("SELECT student_id, SUM(points) as bonus_pts FROM logs WHERE action LIKE '%答题%' GROUP BY student_id", conn)
        conn.close()
        
        bonus_dict = dict(zip(logs_df['student_id'], logs_df['bonus_pts']))
        taken_seats = {(row['row'], row['col']): row for _, row in seats_df.iterrows()}
        
        for r in range(1, ROWS + 1):
            cols_layout = st.columns([1, 1, 0.4, 1, 1, 1, 1, 1, 1, 0.4, 1, 1])
            seat_col_indices = [0, 1, 3, 4, 5, 6, 7, 8, 10, 11]
            
            for c in range(1, COLS + 1):
                ui_col_index = seat_col_indices[c-1]
                
                if (r, c) in taken_seats:
                    seat_data = taken_seats[(r, c)]
                    stu_name = seat_data['student_name']
                    stu_id = seat_data['student_id']
                    
                    base_pts = 2 if r <= VIP_ROWS else 1
                    bonus = bonus_dict.get(stu_id, 0)
                    total_pts = base_pts + bonus
                    
                    if bonus >= 4:
                        bg_color = "#D81B60" 
                        text = f"🔥 {stu_name}<br>({total_pts}分)"
                    elif bonus > 0:
                        bg_color = "#FF9800" 
                        text = f"🌟 {stu_name}<br>({total_pts}分)"
                    elif r <= VIP_ROWS:
                        bg_color = "#FBC02D" 
                        text = f"⭐ {stu_name}<br>({total_pts}分)"
                    else:
                        bg_color = "#4CAF50" 
                        text = f"🧑‍🎓 {stu_name}<br>({total_pts}分)"
                else:
                    if r <= VIP_ROWS:
                        bg_color = "#FFF59D" 
                        text = f"⭐ {r}-{c}"
                    else:
                        bg_color = "#E0E0E0" 
                        text = f"{r}-{c}"
                
                html = f"""<div style="background-color: {bg_color}; padding: 8px 2px; border-radius: 5px; 
                            text-align: center; margin-bottom: 8px; font-weight: bold; color: #333; font-size: 13px;">{text}</div>"""
                cols_layout[ui_col_index].markdown(html, unsafe_allow_html=True)

    with col_side:
        st.header("🏆 排行榜单")
        conn = sqlite3.connect(DB_FILE)
        leaderboard_df = pd.read_sql_query("""
            SELECT student_name, SUM(points) as total_pts 
            FROM logs 
            GROUP BY student_name 
            ORDER BY total_pts DESC 
            LIMIT 5
        """, conn)
        
        if not leaderboard_df.empty:
            for i, row in leaderboard_df.iterrows():
                rank = i + 1
                if rank == 1:
                    title = "👑 榜一"
                    color = "#D32F2F"
                elif rank == 2:
                    title = "🥈 榜二"
                    color = "#E64A19"
                elif rank == 3:
                    title = "🥉 榜三"
                    color = "#F57C00"
                else:
                    title = f"🏅 第 {rank} 名"
                    color = "#388E3C"
                
                st.markdown(f"""
                <div style='background-color: #fff; border: 2px solid {color}; border-radius: 8px; padding: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 16px; font-weight: bold; color: {color};'>{title}</span>
                    <span style='font-size: 18px; font-weight: bold;'>{row['student_name']} <span style='color: #D81B60;'>{row['total_pts']}分</span></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("目前榜单为空，速来打榜！")

        st.markdown("---")
        
        st.subheader("📢 实时动态")
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 6", conn)
        conn.close()
        
        if not logs_df.empty:
            for _, row in logs_df.iterrows():
                time_only = row['timestamp'].split(" ")[1]
                action = row['action']
                
                if "答题" in action:
                    border_color = "#D81B60"
                    icon = "🔥"
                elif "VIP" in action:
                    border_color = "#FBC02D"
                    icon = "⭐"
                else:
                    border_color = "#1E88E5"
                    icon = "🧑‍🎓"
                    
                html_log = f"""
                <div style='margin-bottom: 8px; padding: 8px; border-radius: 5px; background-color: #f8f9fa; border-left: 5px solid {border_color};'>
                    <div style='font-size: 13px; font-weight: bold; color: #333;'>{icon} [{time_only}] {row['student_name']}</div>
                    <div style='font-size: 13px; color: {border_color}; margin-top: 2px;'>{action} (+{row['points']})</div>
                </div>
                """
                st.markdown(html_log, unsafe_allow_html=True)

elif view_mode == "admin":
    # ------------------ 教师隐藏后台 ------------------
    st.title("⚙️ 教师管理后台")
    pwd_input = st.text_input("请输入管理员密码", type="password")
    
    if pwd_input == TEACHER_PWD:
        st.success("✅ 身份验证成功")
        
        st.subheader("1. 课堂控制")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 生成新课堂口令", use_container_width=True):
                new_p = generate_new_pin()
                st.success(f"新口令已生成：{new_p}")
        with col2:
            if is_open:
                if st.button("🛑 关闭签到通道（迟到防刷）", use_container_width=True):
                    update_setting('class_open', 'False')
                    st.rerun()
            else:
                if st.button("🟢 重新开放签到", use_container_width=True):
                    update_setting('class_open', 'True')
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("2. 数据导出与重置 (下课必点！)")
        conn = sqlite3.connect(DB_FILE)
        all_logs_df = pd.read_sql_query("SELECT * FROM logs", conn)
        
        c = conn.cursor()
        c.execute("SELECT class_name FROM seats ORDER BY timestamp ASC LIMIT 1")
        first_class_res = c.fetchone()
        class_label = first_class_res[0] if first_class_res else "未签到班级"
        conn.close()
        
        current_date = datetime.datetime.now(BJ_TZ).strftime('%Y%m%d')
        export_filename = f"class_logs_{current_date}_{class_label}.csv"
        
        st.download_button(
            label="📊 下载今日完整数据日志 (CSV)",
            data=all_logs_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=export_filename,
            mime="text/csv",
            use_container_width=True
        )
        
        st.warning("⚠️ 导出数据后，请清空数据，迎接下一节课。")
        if st.button("🗑️ 清空所有座位和日志 (无法恢复)", type="primary"):
            clear_all_data()
            st.success("数据已清空，大屏幕已重置为全新状态！")
            st.rerun()

else:
    # ------------------ 学生端 ------------------
    st.title("🚀 《学生心理与教育》课堂签到与加分系统")
    
    # 将自动刷新统一放置在页面顶部，并全局生效
    st_autorefresh(interval=5000, limit=None, key="global_student_refresh")
    
    if not is_open:
        st.error("🛑 老师已关闭签到/加分通道。")
        st.stop()
        
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.write("### 身份认证")
            class_name = st.selectbox("学科与班级", CLASSES)
            stu_id = st.text_input("学号")
            stu_name = st.text_input("姓名")
            pin_input = st.text_input("大屏幕【4位口令】")
            submitted = st.form_submit_button("进入系统")
            
            if submitted:
                if pin_input != current_pin:
                    st.error("❌ 口令错误！请抬头看大屏幕。")
                elif not stu_id or not stu_name:
                    st.error("❌ 请填写完整的学号和姓名。")
                else:
                    st.session_state.class_name = class_name
                    st.session_state.stu_id = stu_id
                    st.session_state.stu_name = stu_name
                    st.session_state.logged_in = True
                    st.rerun()
    else:
        st.success(f"你好，{st.session_state.stu_name}")
        
        tab1, tab2, tab3 = st.tabs(["🪑 抢占座位", "🙋 答题加分", "🏆 排行榜单"])
        
        with tab1:
            conn = sqlite3.connect(DB_FILE)
            seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
            conn.close()
            taken_set = set(zip(seats_df['row'], seats_df['col']))
            
            if st.session_state.stu_id in seats_df['student_id'].values:
                st.info("✅ 你已经签到入座，平时分已记录。")
            else:
                available_seats = []
                for r in range(1, ROWS + 1):
                    for c in range(1, COLS + 1):
                        if (r, c) not in taken_set:
                            prefix = "⭐[VIP区+2分]" if r <= VIP_ROWS else "🪑[普通区+1分]"
                            available_seats.append(f"{prefix} {r}排-{c}座")
                
                if available_seats:
                    # 【核心修复：引入表单冻结输入框状态，抵御后台刷新干扰】
                    with st.form("seat_selection_form"):
                        selected_seat = st.selectbox("选择你实际坐的位置：", available_seats)
                        submit_seat = st.form_submit_button("确认入座", type="primary")
                    
                    if submit_seat:
                        parts = selected_seat.split(" ")
                        r = int(parts[1].split("-")[0].replace("排", ""))
                        c = int(parts[1].split("-")[1].replace("座", ""))
                        
                        success, gained_points = take_seat(r, c, st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                        if success:
                            st.success(f"✅ 入座成功！获得 {gained_points} 分！")
                            if gained_points == 2: st.balloons()
                            st.rerun()
                        else:
                            st.error("手慢了，该座位刚被别人抢走，请重新选择！")
                else:
                    st.warning("教室已满座啦！")

        with tab2:
            st.markdown("回答问题后，点击下方按钮自助加分，座位会立刻变色升温！")
            if st.button("🙋 我刚回答了问题，加 2 分！", use_container_width=True):
                add_bonus_points(st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                st.success("✅ 加分成功！速去【排行榜单】页面查看你的排名。")
                
        with tab3:
            st.subheader("🔥 实时排名")
            
            conn = sqlite3.connect(DB_FILE)
            leaderboard_df = pd.read_sql_query("""
                SELECT student_name, SUM(points) as total_pts 
                FROM logs 
                GROUP BY student_name 
                ORDER BY total_pts DESC 
                LIMIT 10
            """, conn)
            conn.close()
            
            if not leaderboard_df.empty:
                for i, row in leaderboard_df.iterrows():
                    rank = i + 1
                    if rank == 1:
                        st.markdown(f"### 👑 榜一：{row['student_name']} ({row['total_pts']}分)")
                        st.progress(min(row['total_pts'] / 10, 1.0)) 
                    elif rank == 2:
                        st.markdown(f"#### 🥈 榜二：{row['student_name']} ({row['total_pts']}分)")
                    elif rank == 3:
                        st.markdown(f"#### 🥉 榜三：{row['student_name']} ({row['total_pts']}分)")
                    else:
                        st.markdown(f"**🏅 第 {rank} 名：** {row['student_name']} ({row['total_pts']}分)")
            else:
                st.info("榜单虚位以待，快去抢座和答题吧！")
                
        # ------------------ 手机端：颜色编码日志看板 ------------------
        st.markdown("---")
        st.subheader("📢 最新动态")
        
        conn = sqlite3.connect(DB_FILE)
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 6", conn)
        conn.close()
        
        for _, row in logs_df.iterrows():
            time_only = row['timestamp'].split(" ")[1]
            action = row['action']
            
            if "答题" in action:
                display_text = f"🔥 <span style='color: #D81B60; font-weight: bold;'>{row['student_name']} {action} (+{row['points']})</span>"
            elif "VIP" in action:
                display_text = f"⭐ <span style='color: #FBC02D; font-weight: bold;'>{row['student_name']} {action} (+{row['points']})</span>"
            else:
                display_text = f"🧑‍🎓 <span style='color: #1E88E5;'>{row['student_name']} {action} (+{row['points']})</span>"
                
            st.markdown(f"[{time_only}] {display_text}", unsafe_allow_html=True)
