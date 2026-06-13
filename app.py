import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os
import re

st.set_page_config(page_title="CML 검색 시스템", layout="wide", page_icon="✈️")

@st.cache_resource
def get_google_sheet_doc(spreadsheet_id):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    current_dir = os.path.dirname(os.path.abspath(__file__))
    key_file = os.path.join(current_dir, "credentials.json")
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        st.error(f"❌ 구글 스프레드시트 연동 실패: {e}")
        return None

@st.cache_data(ttl=600) 
def fetch_code_list(spreadsheet_id, sheet_name):
    doc = get_google_sheet_doc(spreadsheet_id)
    if not doc: return []
    try:
        main_sheet = doc.worksheet(sheet_name)
        data = main_sheet.get_all_values()
        headers = data[0]
        df_main = pd.DataFrame(data[1:], columns=headers)
        
        target_column = next((col for col in df_main.columns if "appl" in str(col).lower()), None)
        if target_column:
            return [c for c in df_main[target_column].str.strip().str.upper().unique().tolist() if c]
        return []
    except:
        return []

def make_table_row(line, col_count):
    """구버전(공백)과 신버전(|) 데이터를 모두 똑똑하게 인식하여 표 칸에 맞게 넣습니다."""
    if "Application Code" in line and "Application Comment" in line: return ""
    if "Product Name" in line and "Airbus Qualified Site" in line: return ""
    
    if '|' in line:
        cells = [cell.strip() for cell in line.split('|')]
    elif '   ' in line or '\t' in line:
        cells = [cell.strip() for cell in re.split(r'\s{3,}|\t', line)]
    else:
        cells = [line.strip()] 

    if not "".join(cells).strip():
        return ""

    # 🌟 [위치 지정 로직] 표의 칸 수에 따라 Old Code의 정확한 위치를 찾아 넣습니다.
    if len(cells) == 1:
        if re.match(r'^\d{2}-[\w\d]{3,4}$', cells[0]):
            if col_count == 5:
                # Application Information 표 (총 5칸) -> Old Code는 3번째 칸
                cells = ['', '', cells[0], '', '']
            elif col_count == 7:
                # Products 표 (총 7칸) -> Old Code는 7번째 칸(맨 끝)
                cells = ['', '', '', '', '', '', cells[0]]
            else:
                cells = [''] * (col_count - 1) + cells
            
    # 혹시 모를 배열 부족 시 에러 방지용 (빈칸 채우기)
    if len(cells) < col_count:
        padding = col_count - len(cells)
        cells = cells + [''] * padding

    row_html = "<tr>"
    for i in range(col_count):
        val = cells[i] if i < len(cells) else ""
        if val == '-': val = "" 
        
        # 🌟 [줄바꿈 로직] 구글 시트의 줄바꿈(\n)을 웹 화면 줄바꿈(<br>)으로 변환
        if isinstance(val, str) and '\n' in val:
            val = val.replace('\n', '<br>')
            
        row_html += f"<td>{val}</td>"
    row_html += "</tr>"
    return row_html

def main():
    st.markdown("""
    <style>
    .airbus-title { font-size: 22px; font-weight: bold; margin-top: 15px; margin-bottom: 20px; color: black; border-bottom: 2px solid black; padding-bottom: 10px;}
    .airbus-section-title { font-size: 16px; font-weight: bold; margin-top: 25px; margin-bottom: 5px; color: black; display: flex; align-items: center;}
    .ac-red { color: red; font-weight: bold; font-style: italic; font-size: 15px; margin-top: 5px; margin-bottom: 8px; }
    .table-container { margin-bottom: 20px; overflow-x: auto; }
    .airbus-table { width: 100%; border-collapse: collapse; font-family: 'Arial', sans-serif; font-size: 13px; text-align: left; border: 1px solid black; }
    .airbus-table th { background-color: #888888; color: black; border: 1px solid black; padding: 6px; text-align: center; font-weight: bold; }
    .airbus-table td { border: 1px solid black; padding: 6px; background-color: white; color: black; vertical-align: middle; }
    .minus-icon { background-color: #888888; color: white; padding: 0px 6px; font-size: 14px; margin-right: 8px; border-radius: 2px; font-weight: bold;}
    </style>
    """, unsafe_allow_html=True)

    st.title("✈️ Airbus CML 데이터 검색 시스템")
    st.markdown("---")
    
    SPREADSHEET_ID = "16OEaLnszCdkZmxvZu_JYTWngAe4sdVoKaOKWzTTPUGk"
    SHEET_NAME = "CML_LIST" 
    
    doc = get_google_sheet_doc(SPREADSHEET_ID)
    if doc is None:
        st.warning("credentials.json 파일을 확인해 주세요.")
        return

    with st.spinner("🔄 구글 시트에서 최신 데이터를 동기화 중입니다... (최초 1회만 소요)"):
        code_list = fetch_code_list(SPREADSHEET_ID, SHEET_NAME)

    col1, col2 = st.columns([1, 1])
    with col1:
        search_code = st.selectbox("📂 수집된 코드 목록에서 선택:", ["선택하세요"] + code_list)
    with col2:
        manual_code = st.text_input("✍️ 또는 직접 입력 (예: 01ABA2):").strip().upper()
    
    final_code = manual_code if manual_code else (search_code if search_code != "선택하세요" else "")

    if final_code:
        st.markdown(f"<div class='airbus-title'>S00 - {final_code} Search Result</div>", unsafe_allow_html=True)
        
        with st.spinner(f"'{final_code}' 데이터를 불러오는 중입니다..."):
            try:
                target_sheet = doc.worksheet(final_code)
                raw_lines = target_sheet.get_all_values()
                
                app_info = []
                products = {}
                obsolete = {}
                
                current_section = None
                current_ac = "** ON A/C ALL"
                
                for row in raw_lines:
                    if not row or not row[0].strip():
                        continue
                        
                    raw_line = row[0]
                    line = raw_line.strip()
                    
                    if "Application Information" in line:
                        current_section = "APP_INFO"
                        continue
                    elif "Products no longer made" in line:
                        current_section = "OBSOLETE"
                        current_ac = "** ON A/C ALL"
                        continue
                    elif "Products" == line:
                        current_section = "PRODUCTS"
                        current_ac = "** ON A/C ALL"
                        continue
                        
                    if line.startswith("** ON A/C"):
                        current_ac = line
                        if current_section == "PRODUCTS" and current_ac not in products:
                            products[current_ac] = []
                        elif current_section == "OBSOLETE" and current_ac not in obsolete:
                            obsolete[current_ac] = []
                        continue
                        
                    if current_section == "APP_INFO":
                        app_info.append(raw_line)
                    elif current_section == "PRODUCTS":
                        if current_ac not in products: products[current_ac] = []
                        products[current_ac].append(raw_line)
                    elif current_section == "OBSOLETE":
                        if current_ac not in obsolete: obsolete[current_ac] = []
                        obsolete[current_ac].append(raw_line)

                # 1. Application Information
                if app_info:
                    st.markdown("<div class='airbus-section-title'>Application Information</div>", unsafe_allow_html=True)
                    rows_html = "".join([make_table_row(item, 5) for item in app_info])
                    
                    app_html = f"""
                    <div class="table-container">
                        <table class="airbus-table">
                            <thead>
                                <tr>
                                    <th style="width: 15%;">Application Code</th>
                                    <th style="width: 35%;">Application</th>
                                    <th style="width: 10%;">Old Code</th>
                                    <th style="width: 5%;">Cat</th>
                                    <th style="width: 35%;">Application Comment</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html if rows_html else "<tr><td colspan='5' style='text-align:center;'>데이터를 표시할 수 없습니다.</td></tr>"}
                            </tbody>
                        </table>
                    </div>
                    """
                    st.markdown(app_html, unsafe_allow_html=True)

                # 2. Products
                if products:
                    st.markdown("<div class='airbus-section-title'><span class='minus-icon'>−</span> Products</div>", unsafe_allow_html=True)
                    for ac, items in products.items():
                        st.markdown(f"<div class='ac-red'>{ac}</div>", unsafe_allow_html=True)
                        rows_html = "".join([make_table_row(item, 7) for item in items])
                        
                        prod_html = f"""
                        <div class="table-container">
                            <table class="airbus-table">
                                <thead>
                                    <tr>
                                        <th style="width: 15%;">Product Name</th>
                                        <th style="width: 15%;">Spec</th>
                                        <th style="width: 25%;">Comment</th>
                                        <th style="width: 10%;">Doc</th>
                                        <th style="width: 15%;">Airbus Qualified Site</th>
                                        <th style="width: 10%;">Product Code</th>
                                        <th style="width: 10%;">Old Code</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows_html if rows_html else "<tr><td colspan='7' style='text-align:center;'>데이터를 표시할 수 없습니다.</td></tr>"}
                                </tbody>
                            </table>
                        </div>
                        """
                        st.markdown(prod_html, unsafe_allow_html=True)

                # 3. Obsolete
                if obsolete:
                    st.markdown("<div class='airbus-section-title'><span class='minus-icon'>−</span> Products no longer made</div>", unsafe_allow_html=True)
                    for ac, items in obsolete.items():
                        st.markdown(f"<div class='ac-red'>{ac}</div>", unsafe_allow_html=True)
                        rows_html = "".join([make_table_row(item, 7) for item in items])

                        obs_html = f"""
                        <div class="table-container">
                            <table class="airbus-table" style="color: #666;">
                                <thead>
                                    <tr>
                                        <th style="width: 15%;">Product Name</th>
                                        <th style="width: 15%;">Spec</th>
                                        <th style="width: 25%;">Comment</th>
                                        <th style="width: 10%;">Doc</th>
                                        <th style="width: 15%;">Airbus Qualified Site</th>
                                        <th style="width: 10%;">Product Code</th>
                                        <th style="width: 10%;">Old Code</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows_html if rows_html else "<tr><td colspan='7' style='text-align:center;'>데이터를 표시할 수 없습니다.</td></tr>"}
                                </tbody>
                            </table>
                        </div>
                        """
                        st.markdown(obs_html, unsafe_allow_html=True)

            except gspread.exceptions.WorksheetNotFound:
                st.error(f"❌ '{final_code}' 시트를 찾을 수 없습니다. 크롤러로 데이터를 수집해 주세요.")
            except Exception as e:
                st.error(f"오류 발생: {e}")
            
    else:
        st.info("👈 위에서 코드를 선택하거나 입력하여 데이터를 조회하세요.")

if __name__ == "__main__":
    main()
