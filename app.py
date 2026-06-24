import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import json
import os

st.set_page_config(page_title="ETF & Aktien Tracker", layout="wide")
st.title("📊 Mein persönlicher Portfolio-Tracker")
st.write("Verwaltung und Analyse von Sektoren, Regionen und Asset-Klassen")

# 1. Daten laden und speichern (Lokal simuliert über JSON-Upload/Download)
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'etf_fallbacks' not in st.session_state:
    st.session_state.etf_fallbacks = {}

# Sidebar für Daten-Backup (Wichtig fürs iPad!)
st.sidebar.header("💾 Daten-Sicherung (iPad)")
uploaded_file = st.sidebar.file_uploader("portfolio.json hochladen", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        st.session_state.portfolio = data.get("portfolio", [])
        st.session_state.etf_fallbacks = data.get("etf_fallbacks", {})
        st.sidebar.success("Daten erfolgreich geladen!")
    except Exception as e:
        st.sidebar.error("Fehler beim Laden der Datei.")

# Export-Button
combined_data = {
    "portfolio": st.session_state.portfolio,
    "etf_fallbacks": st.session_state.etf_fallbacks
}
json_string = json.dumps(combined_data, indent=4)
st.sidebar.download_button(
    label="📥 portfolio.json herunterladen",
    data=json_string,
    file_name="portfolio.json",
    mime="application/json"
)

# 2. Formular für neue Positionen
st.header("➕ Neue Position hinzufügen")
with st.form("add_position_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.text_input("Ticker-Symbol (z.B. AAPL, MSFT, EUNL.DE)").upper().strip()
    with col2:
        shares = st.number_input("Anzahl Anteile", min_value=0.0, step=0.1)
    with col3:
        asset_type = st.selectbox("Asset-Typ", ["Aktie", "ETF"])
        
    submit_btn = st.form_submit_button("Hinzufügen")
    
    if submit_btn and ticker and shares > 0:
        # Prüfen, ob Ticker bereits existiert
        exists = any(item['ticker'] == ticker for item in st.session_state.portfolio)
        if not exists:
            st.session_state.portfolio.append({
                "ticker": ticker,
                "shares": shares,
                "type": asset_type
            })
            st.success(f"{ticker} erfolgreich hinzugefügt!")
            st.rerun()
        else:
            st.warning("Dieses Symbol existiert bereits im Portfolio.")

# 3. Manuelle ETF-Verteilung pflegen (Falls yfinance keine Daten liefert)
etfs_in_portfolio = [p['ticker'] for p in st.session_state.portfolio if p['type'] == "ETF"]
if etfs_in_portfolio:
    st.header("⚙️ ETF-Gewichtungen anpassen (Fallback)")
    st.write("Falls automatische Daten fehlen, kannst du hier die Sektoren und Regionen für deine ETFs in % definieren:")
    
    selected_etf = st.selectbox("Wähle einen ETF zum Bearbeiten", etfs_in_portfolio)
    
    if selected_etf:
        if selected_etf not in st.session_state.etf_fallbacks:
            st.session_state.etf_fallbacks[selected_etf] = {
                "Sektoren": {"Technologie": 100.0},
                "Regionen": {"USA": 100.0}
            }
            
        st.subheader(f"Aufteilung für {selected_etf}")
        
        # Einfache Text-Eingabe für Sektoren/Regionen als JSON-Struktur der Einfachheit halber
        sektoren_text = st.text_area("Sektoren (Format: Name:Prozent, Name:Prozent)", 
                                    value=", ".join([f"{k}:{v}" for k, v in st.session_state.etf_fallbacks[selected_etf]["Sektoren"].items()]))
        regionen_text = st.text_area("Regionen (Format: Name:Prozent, Name:Prozent)", 
                                    value=", ".join([f"{k}:{v}" for k, v in st.session_state.etf_fallbacks[selected_etf]["Regionen"].items()]))
        
        if st.button(f"Gewichtung für {selected_etf} speichern"):
            try:
                new_sek = {item.split(":")[0].strip(): float(item.split(":")[1].strip()) for item in sektoren_text.split(",") if ":" in item}
                new_reg = {item.split(":")[0].strip(): float(item.split(":")[1].strip()) for item in regionen_text.split(",") if ":" in item}
                st.session_state.etf_fallbacks[selected_etf] = {"Sektoren": new_sek, "Regionen": new_reg}
                st.success("ETF-Aufteilung gespeichert!")
                st.rerun()
            except:
                st.error("Fehler im Format. Bitte genau 'Name:Prozent, Name:Prozent' nutzen (z.B. Tech:70, Finanzen:30)")

# 4. Berechnung & Live-Daten Abruf
if st.session_state.portfolio:
    st.header("📈 Portfolio Auswertung")
    
    portfolio_entries = []
    total_portfolio_value = 0.0
    
    # Lade Daten via yfinance
    with st.spinner('Lade aktuelle Marktdaten...'):
        for item in st.session_state.portfolio:
            t = item['ticker']
            shares = item['shares']
            a_type = item['type']
            
            try:
                yf_ticker = yf.Ticker(t)
                # Aktuellen Kurs holen (Fallback auf 1.0 falls Fehler)
                price = yf_ticker.fast_info.get('last_price', None)
                if price is None or pd.isna(price):
                    price = yf_ticker.history(period="1d")['Close'].iloc[-1]
            except:
                price = 10.0 # Dummy Wert falls Ticker offline/falsch
                
            current_value = shares * price
            total_portfolio_value += current_value
            
            # Sektor & Region ermitteln
            sektor_data = {}
            region_data = {}
            
            if a_type == "Aktie":
                try:
                    info = yf_ticker.info
                    sek = info.get('sector', 'Unbekannt')
                    reg = info.get('country', 'Unbekannt')
                    sektor_data[sek] = 100.0
                    region_data[reg] = 100.0
                except:
                    sektor_data['Unbekannt'] = 100.0
                    region_data['Unbekannt'] = 100.0
            else:
                # ETF: Nutze Fallback-Daten falls vorhanden, sonst Unbekannt
                if t in st.session_state.etf_fallbacks:
                    sektor_data = st.session_state.etf_fallbacks[t]["Sektoren"]
                    region_data = st.session_state.etf_fallbacks[t]["Regionen"]
                else:
                    sektor_data['ETF (Unassigned)'] = 100.0
                    region_data['ETF (Unassigned)'] = 100.0
                    
            portfolio_entries.append({
                "ticker": t,
                "type": a_type,
                "value": current_value,
                "sektoren": sektor_data,
                "regionen": region_data
            })

    # Metrik
    st.metric("Gesamtwert des Portfolios", f"{total_portfolio_value:,.2f} €")
    
    # Tabellarische Übersicht mit Löschen-Option
    st.subheader("Aktuelle Positionen")
    df_view = pd.DataFrame([{
        "Ticker": p["ticker"], 
        "Typ": p["type"], 
        "Wert (€)": f"{p['value']:,.2f}"
    } for p in portfolio_entries])
    st.dataframe(df_view, use_container_width=True)
    
    # Positionen löschen
    to_delete = st.selectbox("Position löschen?", ["-"] + [p['ticker'] for p in st.session_state.portfolio])
    if to_delete != "-":
        st.session_state.portfolio = [p for p in st.session_state.portfolio if p['ticker'] != to_delete]
        st.success(f"{to_delete} entfernt.")
        st.rerun()

    # Aggregation für die Charts
    asset_dist = {"Aktie": 0.0, "ETF": 0.0}
    sektor_dist = {}
    region_dist = {}
    
    for p in portfolio_entries:
        val = p["value"]
        asset_dist[p["type"]] += val
        
        # Sektoren gewichtet aufteilen
        for sek, proz in p["sektoren"].items():
            anteil = val * (proz / 100.0)
            sektor_dist[sek] = sektor_dist.get(sek, 0.0) + anteil
            
        # Regionen gewichtet aufteilen
        for reg, proz in p["regionen"].items():
            anteil = val * (proz / 100.0)
            region_dist[reg] = region_dist.get(reg, 0.0) + anteil

    # Charts anzeigen
    st.write("---")
    chart_col1, chart_col2, chart_col3 = st.columns(3)
    
    with chart_col1:
        st.subheader("Asset-Klassen (%)")
        df_asset = pd.DataFrame(list(asset_dist.items()), columns=['Klasse', 'Wert'])
        fig_asset = px.pie(df_asset, names='Klasse', values='Wert', hole=0.4)
        st.plotly_chart(fig_asset, use_container_width=True)
        
    with chart_col2:
        st.subheader("Sektorengewichtung (%)")
        df_sek = pd.DataFrame(list(sektor_dist.items()), columns=['Sektor', 'Wert'])
        fig_sek = px.pie(df_sek, names='Sektor', values='Wert', hole=0.4)
        st.plotly_chart(fig_sek, use_container_width=True)
        
    with chart_col3:
        st.subheader("Regionengewichtung (%)")
        df_reg = pd.DataFrame(list(region_dist.items()), columns=['Region', 'Wert'])
        fig_reg = px.pie(df_reg, names='Region', values='Wert', hole=0.4)
        st.plotly_chart(fig_reg, use_container_width=True)

else:
    st.info("Dein Portfolio ist aktuell noch leer. Füge oben oder über ein Backup Positionen hinzu.")
