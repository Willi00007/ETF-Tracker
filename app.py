"""
Lokaler Portfolio-Tracker
=========================
Anforderungen installieren:
    pip install streamlit pandas yfinance plotly
 
Starten:
    streamlit run portfolio_tracker.py
"""
 
import json
import os
import time
from datetime import datetime
from typing import Optional
 
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
 
# ─────────────────────────────────────────────
# Konstanten & Konfiguration
# ─────────────────────────────────────────────
 
PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio.json")
 
SECTOR_MAP_DE = {
    "Technology": "Technologie",
    "Financial Services": "Finanzen",
    "Healthcare": "Gesundheit",
    "Consumer Cyclical": "Zyklischer Konsum",
    "Consumer Defensive": "Nicht-zyklischer Konsum",
    "Industrials": "Industrie",
    "Communication Services": "Kommunikation",
    "Energy": "Energie",
    "Basic Materials": "Rohstoffe",
    "Real Estate": "Immobilien",
    "Utilities": "Versorger",
}
 
REGION_COLORS = {
    "USA": "#3B82F6",
    "Europa": "#10B981",
    "Schwellenländer": "#F59E0B",
    "Japan": "#EF4444",
    "Kanada": "#8B5CF6",
    "Pazifik": "#06B6D4",
    "Andere": "#6B7280",
}
 
SECTOR_COLORS = {
    "Technologie": "#6366F1",
    "Finanzen": "#3B82F6",
    "Gesundheit": "#10B981",
    "Industrie": "#F59E0B",
    "Zyklischer Konsum": "#EF4444",
    "Nicht-zyklischer Konsum": "#8B5CF6",
    "Kommunikation": "#EC4899",
    "Energie": "#F97316",
    "Rohstoffe": "#84CC16",
    "Immobilien": "#14B8A6",
    "Versorger": "#A78BFA",
    "Sonstige": "#6B7280",
}
 
# ─────────────────────────────────────────────
# JSON-Datenverwaltung
# ─────────────────────────────────────────────
 
def load_portfolio() -> dict:
    """Lädt das Portfolio aus der lokalen JSON-Datei."""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"positions": [], "etf_metadata": {}}
    return {"positions": [], "etf_metadata": {}}
 
 
def save_portfolio(data: dict) -> None:
    """Speichert das Portfolio in die lokale JSON-Datei."""
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
 
# ─────────────────────────────────────────────
# yfinance Datenabruf
# ─────────────────────────────────────────────
 
@st.cache_data(ttl=300, show_spinner=False)
def fetch_ticker_info(ticker: str) -> Optional[dict]:
    """Ruft Ticker-Metadaten via yfinance ab (gecacht für 5 min)."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or "regularMarketPrice" not in info:
            return None
        return info
    except Exception:
        return None
 
 
@st.cache_data(ttl=60, show_spinner=False)
def fetch_current_price(ticker: str) -> Optional[float]:
    """Ruft den aktuellen Kurs via yfinance ab."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        price = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("navPrice")
        )
        return float(price) if price else None
    except Exception:
        return None
 
 
def classify_asset(info: dict) -> str:
    """Klassifiziert einen Ticker als 'ETF' oder 'Aktie'."""
    q_type = info.get("quoteType", "").upper()
    if q_type in ("ETF", "MUTUALFUND"):
        return "ETF"
    return "Aktie"
 
 
def get_sector_from_info(info: dict) -> Optional[str]:
    """Extrahiert den Sektor einer Aktie (englisch → deutsch)."""
    sector_en = info.get("sector")
    if not sector_en:
        return None
    return SECTOR_MAP_DE.get(sector_en, sector_en)
 
 
def get_region_from_info(info: dict) -> Optional[str]:
    """Ermittelt die Region/Land einer Aktie."""
    country = info.get("country", "")
    if not country:
        return None
    country_to_region = {
        "United States": "USA",
        "Canada": "Kanada",
        "Germany": "Europa",
        "France": "Europa",
        "United Kingdom": "Europa",
        "Switzerland": "Europa",
        "Netherlands": "Europa",
        "Sweden": "Europa",
        "Denmark": "Europa",
        "Spain": "Europa",
        "Italy": "Europa",
        "Norway": "Europa",
        "Finland": "Europa",
        "Belgium": "Europa",
        "Austria": "Europa",
        "Japan": "Japan",
        "China": "Schwellenländer",
        "India": "Schwellenländer",
        "Brazil": "Schwellenländer",
        "South Korea": "Schwellenländer",
        "Taiwan": "Schwellenländer",
        "Australia": "Pazifik",
        "Hong Kong": "Pazifik",
        "Singapore": "Pazifik",
        "New Zealand": "Pazifik",
    }
    return country_to_region.get(country, "Andere")
 
 
# ─────────────────────────────────────────────
# Portfolio-Berechnungen
# ─────────────────────────────────────────────
 
def build_enriched_positions(portfolio: dict) -> list[dict]:
    """
    Reichert jede Position mit Live-Kurs, Gesamtwert,
    Asset-Typ, Sektor und Region an.
    """
    enriched = []
    for pos in portfolio.get("positions", []):
        ticker = pos["ticker"]
        shares = pos["shares"]
        buy_price = pos.get("buy_price")
 
        info = fetch_ticker_info(ticker)
        price = None
        asset_type = "Unbekannt"
        sector = None
        region = None
 
        if info:
            price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("navPrice")
            )
            if price:
                price = float(price)
            asset_type = classify_asset(info)
            sector = get_sector_from_info(info)
            region = get_region_from_info(info)
 
        total_value = (price * shares) if price else None
 
        pnl = None
        pnl_pct = None
        if price and buy_price:
            pnl = (price - buy_price) * shares
            pnl_pct = ((price - buy_price) / buy_price) * 100
 
        # ETF-Metadaten aus Portfolio
        etf_meta = portfolio.get("etf_metadata", {}).get(ticker, {})
 
        enriched.append({
            "ticker": ticker,
            "name": info.get("shortName", ticker) if info else ticker,
            "shares": shares,
            "buy_price": buy_price,
            "current_price": price,
            "total_value": total_value,
            "asset_type": asset_type,
            "sector": sector,
            "region": region,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "etf_sectors": etf_meta.get("sectors", {}),
            "etf_regions": etf_meta.get("regions", {}),
            "has_etf_meta": bool(etf_meta),
            "currency": info.get("currency", "—") if info else "—",
        })
    return enriched
 
 
def compute_aggregate_weights(enriched: list[dict]) -> dict:
    """
    Berechnet Sektor-, Regionen- und Asset-Klassen-Gewichtungen
    als prozentuale Anteile am Gesamtportfolio.
    """
    total = sum(p["total_value"] for p in enriched if p["total_value"])
    if total == 0:
        return {"sectors": {}, "regions": {}, "asset_types": {}, "total": 0}
 
    sectors: dict[str, float] = {}
    regions: dict[str, float] = {}
    asset_types: dict[str, float] = {}
 
    for pos in enriched:
        val = pos["total_value"]
        if not val:
            continue
 
        weight = val / total  # Anteil am Gesamtportfolio (0–1)
 
        # ── Asset-Typ ──────────────────────────────────────────
        at = pos["asset_type"]
        asset_types[at] = asset_types.get(at, 0) + weight * 100
 
        # ── Sektor ────────────────────────────────────────────
        if pos["asset_type"] == "ETF" and pos["etf_sectors"]:
            for sector, pct in pos["etf_sectors"].items():
                contribution = weight * pct  # in Prozent des Gesamtportfolios
                sectors[sector] = sectors.get(sector, 0) + contribution
        elif pos["sector"]:
            sectors[pos["sector"]] = sectors.get(pos["sector"], 0) + weight * 100
 
        # ── Region ────────────────────────────────────────────
        if pos["asset_type"] == "ETF" and pos["etf_regions"]:
            for region, pct in pos["etf_regions"].items():
                contribution = weight * pct
                regions[region] = regions.get(region, 0) + contribution
        elif pos["region"]:
            regions[pos["region"]] = regions.get(pos["region"], 0) + weight * 100
 
    return {
        "sectors": sectors,
        "regions": regions,
        "asset_types": asset_types,
        "total": total,
    }
 
 
# ─────────────────────────────────────────────
# Plotly-Charts
# ─────────────────────────────────────────────
 
def make_pie_chart(labels: list, values: list, title: str, color_map: Optional[dict] = None) -> go.Figure:
    """Erstellt ein einheitlich gestaltetes Plotly-Kuchendiagramm."""
    colors = [color_map.get(l, "#6B7280") for l in labels] if color_map else None
 
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.42,
            textinfo="label+percent",
            textfont=dict(size=13),
            marker=dict(colors=colors, line=dict(color="#1E293B", width=2)),
            hovertemplate="<b>%{label}</b><br>%{percent:.1%} (%{value:.1f}%)<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#F1F5F9"), x=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1"),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=50, b=10, l=10, r=10),
        height=380,
    )
    return fig
 
 
# ─────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────
 
def main():
    st.set_page_config(
        page_title="Portfolio Tracker",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
 
    # ── Custom CSS ──────────────────────────────────────────────
    st.markdown("""
    <style>
        /* Hintergrund & Basisfarben */
        .stApp { background-color: #0F172A; color: #E2E8F0; }
        section[data-testid="stSidebar"] { background-color: #1E293B; }
 
        /* Metriken */
        [data-testid="metric-container"] {
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 14px 18px;
        }
        [data-testid="metric-container"] label { color: #94A3B8 !important; font-size: 0.8rem; }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #F1F5F9 !important; font-size: 1.4rem; font-weight: 700;
        }
 
        /* Tabelle */
        .dataframe { background-color: #1E293B !important; color: #E2E8F0 !important; }
 
        /* Buttons */
        .stButton > button {
            background: #3B82F6; color: white; border: none;
            border-radius: 8px; padding: 0.45rem 1.1rem; font-weight: 600;
        }
        .stButton > button:hover { background: #2563EB; }
 
        /* Trennlinie */
        hr { border-color: #334155; }
 
        /* Header-Bereich */
        .portfolio-header {
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px 28px;
            margin-bottom: 24px;
        }
        .portfolio-header h1 { color: #F1F5F9; margin: 0; font-size: 1.8rem; }
        .portfolio-header p  { color: #94A3B8; margin: 4px 0 0; font-size: 0.9rem; }
 
        /* Warning-Box */
        .needs-meta {
            background: #1C1917; border-left: 3px solid #F59E0B;
            border-radius: 6px; padding: 10px 14px; margin: 8px 0;
            color: #FDE68A; font-size: 0.88rem;
        }
    </style>
    """, unsafe_allow_html=True)
 
    # ── Session State ────────────────────────────────────────────
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = load_portfolio()
 
    portfolio = st.session_state.portfolio
 
    # ── Header ──────────────────────────────────────────────────
    st.markdown("""
    <div class="portfolio-header">
        <h1>📈 Portfolio Tracker</h1>
        <p>Lokale Analyse · Keine Cloud · Alle Daten in portfolio.json</p>
    </div>
    """, unsafe_allow_html=True)
 
    # ════════════════════════════════════════════════════════════
    # SIDEBAR – Position hinzufügen
    # ════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("## ➕ Position hinzufügen")
 
        with st.form("add_position", clear_on_submit=True):
            ticker_input = st.text_input(
                "Ticker-Symbol",
                placeholder="z.B. AAPL, EUNL.DE, IWDA.AS",
                help="Ticker so eingeben wie auf Yahoo Finance",
            ).upper().strip()
            shares_input = st.number_input("Anzahl Anteile", min_value=0.0001, step=0.01, format="%.4f")
            buy_price_input = st.number_input(
                "Kaufkurs (optional)", min_value=0.0, step=0.01, format="%.2f", value=0.0
            )
            submitted = st.form_submit_button("💾 Speichern", use_container_width=True)
 
        if submitted and ticker_input:
            existing = [p["ticker"] for p in portfolio["positions"]]
            if ticker_input in existing:
                st.sidebar.warning(f"**{ticker_input}** ist bereits im Portfolio.")
            else:
                new_pos = {
                    "ticker": ticker_input,
                    "shares": shares_input,
                    "buy_price": buy_price_input if buy_price_input > 0 else None,
                    "added": datetime.now().isoformat(),
                }
                portfolio["positions"].append(new_pos)
                save_portfolio(portfolio)
                st.cache_data.clear()
                st.sidebar.success(f"✅ **{ticker_input}** hinzugefügt!")
                st.rerun()
 
        st.markdown("---")
        st.markdown("### 🗂 Meine Positionen")
 
        if portfolio["positions"]:
            for i, pos in enumerate(portfolio["positions"]):
                col1, col2 = st.sidebar.columns([4, 1])
                with col1:
                    st.markdown(f"**{pos['ticker']}** – {pos['shares']:.4g} Stk.")
                with col2:
                    if st.button("🗑", key=f"del_{i}", help=f"{pos['ticker']} löschen"):
                        ticker_to_remove = pos["ticker"]
                        portfolio["positions"].pop(i)
                        portfolio.get("etf_metadata", {}).pop(ticker_to_remove, None)
                        save_portfolio(portfolio)
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.info("Noch keine Positionen.")
 
        st.markdown("---")
        if st.button("🔄 Kurse aktualisieren", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
 
        st.caption(f"Datei: `{PORTFOLIO_FILE}`")
 
    # ════════════════════════════════════════════════════════════
    # HAUPTBEREICH
    # ════════════════════════════════════════════════════════════
    if not portfolio["positions"]:
        st.info("📭 Noch keine Positionen. Füge links in der Sidebar deine erste Aktie oder ETF hinzu.")
        return
 
    # ── Daten laden ─────────────────────────────────────────────
    with st.spinner("Kurse werden abgerufen …"):
        enriched = build_enriched_positions(portfolio)
        weights = compute_aggregate_weights(enriched)
 
    total_value = weights["total"]
    total_cost = sum(
        p["buy_price"] * p["shares"]
        for p in enriched
        if p["buy_price"] and p["shares"]
    )
    total_pnl = total_value - total_cost if total_cost else None
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost and total_pnl is not None else None
 
    # ── KPI-Kacheln ─────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📦 Gesamtwert", f"{total_value:,.2f} €" if total_value else "—")
    k2.metric("📊 Positionen", len(enriched))
    k3.metric(
        "📈 Gewinn/Verlust",
        f"{total_pnl:+,.2f} €" if total_pnl is not None else "—",
        delta=f"{total_pnl_pct:+.2f}%" if total_pnl_pct is not None else None,
    )
    k4.metric(
        "🏷 Einstandswert",
        f"{total_cost:,.2f} €" if total_cost else "—",
    )
 
    st.markdown("---")
 
    # ════════════════════════════════════════════════════════════
    # ETF-Metadaten Eingabe (Fallback)
    # ════════════════════════════════════════════════════════════
    etf_without_meta = [
        p for p in enriched
        if p["asset_type"] == "ETF" and not p["has_etf_meta"]
    ]
 
    if etf_without_meta:
        st.markdown("### ⚠️ ETF-Gewichtungen manuell eintragen")
        st.markdown(
            "Für folgende ETFs konnten keine automatischen Sektor-/Regionen-Daten abgerufen werden. "
            "Trage die Gewichtungen einmalig ein – sie werden lokal gespeichert."
        )
 
        for pos in etf_without_meta:
            ticker = pos["ticker"]
            with st.expander(f"🔧 {ticker} – {pos['name']} konfigurieren", expanded=True):
                st.markdown(f"<div class='needs-meta'>Keine automatischen Daten für <b>{ticker}</b> verfügbar.</div>",
                            unsafe_allow_html=True)
 
                tab_sec, tab_reg = st.tabs(["Sektorgewichtung (%)", "Regionengewichtung (%)"])
 
                default_sectors = {
                    "Technologie": 0, "Finanzen": 0, "Gesundheit": 0,
                    "Industrie": 0, "Zyklischer Konsum": 0, "Nicht-zyklischer Konsum": 0,
                    "Kommunikation": 0, "Energie": 0, "Rohstoffe": 0,
                    "Immobilien": 0, "Versorger": 0,
                }
                default_regions = {
                    "USA": 0, "Europa": 0, "Schwellenländer": 0,
                    "Japan": 0, "Kanada": 0, "Pazifik": 0, "Andere": 0,
                }
 
                existing_meta = portfolio.get("etf_metadata", {}).get(ticker, {})
 
                with tab_sec:
                    sector_values = {}
                    cols = st.columns(3)
                    for idx, (sec, default) in enumerate(default_sectors.items()):
                        with cols[idx % 3]:
                            sector_values[sec] = st.number_input(
                                sec,
                                min_value=0.0, max_value=100.0,
                                value=float(existing_meta.get("sectors", {}).get(sec, default)),
                                step=0.5, key=f"sec_{ticker}_{sec}",
                            )
                    sec_total = sum(sector_values.values())
                    if abs(sec_total - 100) > 0.1 and sec_total > 0:
                        st.warning(f"Summe der Sektoren: {sec_total:.1f}% (sollte 100% ergeben)")
                    elif sec_total > 0:
                        st.success(f"✅ Summe: {sec_total:.1f}%")
 
                with tab_reg:
                    region_values = {}
                    cols = st.columns(3)
                    for idx, (reg, default) in enumerate(default_regions.items()):
                        with cols[idx % 3]:
                            region_values[reg] = st.number_input(
                                reg,
                                min_value=0.0, max_value=100.0,
                                value=float(existing_meta.get("regions", {}).get(reg, default)),
                                step=0.5, key=f"reg_{ticker}_{reg}",
                            )
                    reg_total = sum(region_values.values())
                    if abs(reg_total - 100) > 0.1 and reg_total > 0:
                        st.warning(f"Summe der Regionen: {reg_total:.1f}% (sollte 100% ergeben)")
                    elif reg_total > 0:
                        st.success(f"✅ Summe: {reg_total:.1f}%")
 
                if st.button(f"💾 {ticker}-Daten speichern", key=f"save_meta_{ticker}"):
                    if "etf_metadata" not in portfolio:
                        portfolio["etf_metadata"] = {}
                    portfolio["etf_metadata"][ticker] = {
                        "sectors": {k: v for k, v in sector_values.items() if v > 0},
                        "regions": {k: v for k, v in region_values.items() if v > 0},
                    }
                    save_portfolio(portfolio)
                    st.cache_data.clear()
                    st.success(f"✅ Daten für {ticker} gespeichert!")
                    time.sleep(0.5)
                    st.rerun()
 
        st.markdown("---")
 
    # ════════════════════════════════════════════════════════════
    # DASHBOARD – Charts
    # ════════════════════════════════════════════════════════════
    st.markdown("### 📊 Portfolio-Analyse")
 
    ch1, ch2, ch3 = st.columns(3)
 
    # ── Asset-Klassen ────────────────────────────────────────────
    with ch1:
        at_data = weights["asset_types"]
        if at_data:
            fig = make_pie_chart(
                labels=list(at_data.keys()),
                values=list(at_data.values()),
                title="Asset-Klassen",
                color_map={"ETF": "#3B82F6", "Aktie": "#10B981", "Unbekannt": "#6B7280"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Asset-Klassen-Daten.")
 
    # ── Sektorgewichtung ─────────────────────────────────────────
    with ch2:
        sec_data = weights["sectors"]
        if sec_data:
            fig = make_pie_chart(
                labels=list(sec_data.keys()),
                values=list(sec_data.values()),
                title="Sektorgewichtung",
                color_map=SECTOR_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Sektor-Daten verfügbar.\nTrage ETF-Gewichtungen oben ein.")
 
    # ── Regionengewichtung ───────────────────────────────────────
    with ch3:
        reg_data = weights["regions"]
        if reg_data:
            fig = make_pie_chart(
                labels=list(reg_data.keys()),
                values=list(reg_data.values()),
                title="Regionengewichtung",
                color_map=REGION_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Regionen-Daten verfügbar.\nTrage ETF-Gewichtungen oben ein.")
 
    # ════════════════════════════════════════════════════════════
    # POSITIONSTABELLE
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📋 Positionen im Detail")
 
    rows = []
    for p in enriched:
        pnl_str = f"{p['pnl']:+.2f} {p['currency']}" if p["pnl"] is not None else "—"
        pnl_pct_str = f"{p['pnl_pct']:+.2f}%" if p["pnl_pct"] is not None else "—"
        rows.append({
            "Ticker": p["ticker"],
            "Name": p["name"],
            "Typ": p["asset_type"],
            "Anteile": f"{p['shares']:.4g}",
            "Kaufkurs": f"{p['buy_price']:.2f} {p['currency']}" if p["buy_price"] else "—",
            "Kurs aktuell": f"{p['current_price']:.2f} {p['currency']}" if p["current_price"] else "Fehler",
            "Gesamtwert": f"{p['total_value']:,.2f} {p['currency']}" if p["total_value"] else "—",
            "G/V": pnl_str,
            "G/V %": pnl_pct_str,
            "Sektor/ETF": p["sector"] or ("ETF (manuell)" if p["has_etf_meta"] else "ETF (ausstehend)"),
            "Region": p["region"] or ("—"),
        })
 
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
 
    # ════════════════════════════════════════════════════════════
    # SEKTOR & REGION – Balkendarstellung (Detail)
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📐 Detailansicht Gewichtungen")
 
    d1, d2 = st.columns(2)
 
    with d1:
        if weights["sectors"]:
            sec_df = (
                pd.DataFrame.from_dict(weights["sectors"], orient="index", columns=["Anteil (%)"])
                .sort_values("Anteil (%)", ascending=True)
            )
            fig_bar = px.bar(
                sec_df,
                x="Anteil (%)",
                y=sec_df.index,
                orientation="h",
                title="Sektoren – Balkendiagramm",
                color=sec_df.index,
                color_discrete_map=SECTOR_COLORS,
                text_auto=".1f",
            )
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#CBD5E1"),
                showlegend=False,
                margin=dict(t=50, b=10, l=10, r=30),
                title=dict(font=dict(color="#F1F5F9")),
                xaxis=dict(gridcolor="#334155"),
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
                height=400,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
 
    with d2:
        if weights["regions"]:
            reg_df = (
                pd.DataFrame.from_dict(weights["regions"], orient="index", columns=["Anteil (%)"])
                .sort_values("Anteil (%)", ascending=True)
            )
            fig_bar2 = px.bar(
                reg_df,
                x="Anteil (%)",
                y=reg_df.index,
                orientation="h",
                title="Regionen – Balkendiagramm",
                color=reg_df.index,
                color_discrete_map=REGION_COLORS,
                text_auto=".1f",
            )
            fig_bar2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#CBD5E1"),
                showlegend=False,
                margin=dict(t=50, b=10, l=10, r=30),
                title=dict(font=dict(color="#F1F5F9")),
                xaxis=dict(gridcolor="#334155"),
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
                height=400,
            )
            st.plotly_chart(fig_bar2, use_container_width=True)
 
    # Footer
    st.markdown("---")
    st.caption(
        f"🕐 Letzter Abruf: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} · "
        "Kursdaten via yfinance · Kurs-Cache: 5 Min. · "
        f"Daten lokal gespeichert in `{PORTFOLIO_FILE}`"
    )
 
 
if __name__ == "__main__":
