import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import json

st.set_page_config(page_title="ETF & Aktien Tracker", layout="wide")
st.title("📊 Mein persönlicher Portfolio-Tracker")
st.write("Verwaltung und Analyse von Sektoren, Regionen und Asset-Klassen")

# Daten-Struktur im Hintergrund initialisieren
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'custom_mappings' not in st.session_state:
    st.session_state.custom_mappings = {}

# Sidebar für Daten-Backup (Wichtig fürs iPad!)
st.sidebar.header("💾 Daten-Sicherung (iPad)")
uploaded_file = st.sidebar.file_uploader("portfolio.json hochladen", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        st.session_state.portfolio = data.get("portfolio", [])
        st.session_state.custom_mappings = data.get("custom_mappings", {})
        st.sidebar.success("Daten erfolgreich geladen!")
    except:
        st.sidebar.error("Fehler beim Laden der Datei.")

# Export-Daten vorbereiten
combined_data = {
    "portfolio": st.session_state.portfolio,
    "custom_mappings": st.session_state.custom_mappings
}
json_string = json.dumps(combined_data, indent=4)
st.sidebar.download_button(
    label="📥 portfolio.json herunterladen",
    data=json_string,
    file_name="portfolio.json",
    mime="application/json"
)

# Formular für neue Positionen
st.header("➕ Neue Position hinzufügen")
with st.form("add_position_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.text_input("Ticker-Symbol (z.B. AAPL, MSFT, NL0011683594.SG)").strip()
    with col2:
        shares = st.number_input("Anzahl Anteile", min_value=0.0, step=0.01, format="%.4f")
    with col3:
        asset_type = st.selectbox("Asset-Typ", ["Aktie", "ETF"])
        
    submit_btn = st.form_submit_button("Hinzufügen")
    
    if submit_btn and ticker and shares > 0:
        exists = any(item['ticker'].upper() == ticker.upper() for item in st.session_state.portfolio)
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

# Manuelle Gewichtungen pflegen für Positionen, bei denen die API keine Daten liefert
if st.session_state.portfolio:
    st.header("⚙️ Manuelle Gewichtungen & Korrekturen")
    st.write("Falls Live-Daten fehlen oder falsch sind, kannst du hier die Verteilung in % korrigieren:")
    
    all_tickers = [p['ticker'] for p in st.session_state.portfolio]
    selected_ticker = st.selectbox("Wähle eine Position zum Bearbeiten", all_tickers)
    
    if selected_ticker:
        if selected_ticker not in st.session_state.custom_mappings:
            st.session_state.custom_mappings[selected_ticker] = {
                "Kurs": 0.0,
                "Sektoren": "Unbekannt:100",
                "Regionen": "Unbekannt:100"
            }
            
        st.subheader(f"Manuelle Werte für {selected_ticker}")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            manual_price = st.number_input("Manueller Kurs (0.0 = Live-Kurs nutzen)", 
                                           min_value=0.0, 
                                           value=float(st.session_state.custom_mappings[selected_ticker].get("Kurs", 0.0)),
                                           step=0.01)
        with col_c2:
            sektoren_text = st.text_area("Sektoren (Format: Name:Prozent, ...)", 
                                        value=st.session_state.custom_mappings[selected_ticker].get("Sektoren", "Unbekannt:100"))
        with col_c3:
            regionen_text = st.text_area("Regionen (Format: Name:Prozent, ...)", 
                                        value=st.session_state.custom_mappings[selected_ticker].get("Regionen", "Unbekannt:100"))
            
        if st.button(f"Änderungen für {selected_ticker} speichern"):
            st.session_state.custom_mappings[selected_ticker] = {
                "Kurs": manual_price,
                "Sektoren": sektoren_text,
                "Regionen": regionen_text
            }
            st.success("Erfolgreich gespeichert!")
            st.rerun()

# Auswertung & Berechnung
if st.session_state.portfolio:
    st.header("📈 Portfolio Auswertung")
    
    portfolio_entries = []
    total_portfolio_value = 0.0
    
    with st.spinner('Lade aktuelle Marktdaten...'):
        for item in st.session_state.portfolio:
            t = item['ticker']
            shares = item['shares']
            a_type = item['type']
            
            # 1. Kurs ermitteln (Manuell vs. Live)
            custom_data = st.session_state.custom_mappings.get(t, {})
            price = custom_data.get("Kurs", 0.0)
            
            if price == 0.0: # Wenn kein manueller Kurs gesetzt ist, live laden
                try:
                    yf_ticker = yf.Ticker(t)
                    # Gründlichere Kursabfrage über Historie
                    hist = yf_ticker.history(period="1d")
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                    else:
                        price = float(yf_ticker.fast_info.get('last_price', 0.0))
                except:
                    price = 0.0
            
            # Falls immer noch 0, weisen wir den User darauf hin
            current_value = shares * price
            total_portfolio_value += current_value
            
            # 2. Sektoren & Regionen aufteilen
            sektor_dist = {}
            region_dist = {}
            
            # Prüfen, ob der Nutzer manuelle Text-Verteilungen eingegeben hat und diese ungleich "Unbekannt:100" sind
            has_custom_sek = "Unbekannt:100" not in custom_data.get("Sektoren", "Unbekannt:100")
            has_custom_reg = "Unbekannt:100" not in custom_data.get("Regionen", "Unbekannt:100")
            
            # Sektoren ermitteln
            if has_custom_sek:
                try:
                    for s_item in custom_data["Sektoren"].split(","):
                        if ":" in s_item:
                            k, v = s_item.split(":")
                            sektor_dist[k.strip()] = float(v.strip())
                except:
                    sektor_dist["Fehler im Format"] = 100.0
            else:
                # Versuchen live zu laden (nur bei Aktien sinnvoll)
                if a_type == "Aktie":
                    try:
                        yf_ticker = yf.Ticker(t)
                        sek = yf_ticker.info.get('sector', 'Unbekannt')
                        sektor_dist[sek] = 100.0
                    except:
                        sektor_dist["Unbekannt / API fehlt"] = 100.0
                else:
                    sektor_dist["ETF (Nicht zugewiesen)"] = 100.0
                    
            # Regionen ermitteln
            if has_custom_reg:
                try:
                    for r_item in custom_data["Regionen"].split(","):
                        if ":" in r_item:
                            k, v = r_item.split(":")
                            region_dist[k.strip()] = float(v.strip())
                except:
                    region_dist["Fehler im Format"] = 100.0
            else:
                if a_type == "Aktie":
                    try:
                        yf_ticker = yf.Ticker(t)
                        reg = yf_ticker.info.get('country', 'Unbekannt')
                        region_dist[reg] = 100.0
                    except:
                        region_dist["Unbekannt / API fehlt"] = 100.0
                else:
                    region_dist["ETF (Nicht zugewiesen)"] = 100.0

            portfolio_entries.append({
                "ticker": t,
                "type": a_type,
                "value": current_value,
                "price": price,
                "sektoren": sektor_dist,
                "regionen": region_dist
            })

    # Gesamtwert anzeigen
    st.metric("Gesamtwert des Portfolios", f"{total_portfolio_value:,.2f} €")
    
    # Tabelle anzeigen
    df_view = pd.DataFrame([{
        "Ticker": p["ticker"], 
        "Typ": p["type"], 
        "Aktueller Kurs": f"{p['price']:,.2f} €",
        "Gesamtwert": f"{p['value']:,.2f} €"
    } for p in portfolio_entries])
    st.dataframe(df_view, use_container_width=True)
    
    # Löschen-Funktion
    to_delete = st.selectbox("Position löschen?", ["-"] + all_tickers)
    if to_delete != "-":
        st.session_state.portfolio = [p for p in st.session_state.portfolio if p['ticker'] != to_delete]
        if to_delete in st.session_state.custom_mappings:
            del st.session_state.custom_mappings[to_delete]
        st.success(f"{to_delete} entfernt.")
        st.rerun()

    # Diagramm-Daten aggregieren
    asset_dist = {"Aktie": 0.0, "ETF": 0.0}
    total_sektoren = {}
    total_regionen = {}
    
    for p in portfolio_entries:
        val = p["value"]
        asset_dist[p["type"]] += val
        
        for sek, proz in p["sektoren"].items():
            total_sektoren[sek] = total_sektoren.get(sek, 0.0) + (val * (proz / 100.0))
            
        for reg, proz in p["regionen"].items():
            total_regionen[reg] = total_regionen.get(reg, 0.0) + (val * (proz / 100.0))

    # Charts zeichnen
    st.write("---")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Asset-Klassen (%)")
        df_a = pd.DataFrame(list(asset_dist.items()), columns=['Klasse', 'Wert'])
        st.plotly_chart(px.pie(df_a, names='Klasse', values='Wert', hole=0.4), use_container_width=True)
        
    with c2:
        st.subheader("Sektorengewichtung (%)")
        df_s = pd.DataFrame(list(total_sektoren.items()), columns=['Sektor', 'Wert'])
        st.plotly_chart(px.pie(df_s, names='Sektor', values='Wert', hole=0.4), use_container_width=True)
        
    with c3:
        st.subheader("Regionengewichtung (%)")
        df_r = pd.DataFrame(list(total_regionen.items()), columns=['Region', 'Wert'])
        st.plotly_chart(px.pie(df_r, names='Region', values='Wert', hole=0.4), use_container_width=True)
else:
    st.info("Dein Portfolio ist leer.")
