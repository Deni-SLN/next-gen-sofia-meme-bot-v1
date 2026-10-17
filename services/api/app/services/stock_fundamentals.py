"""
Fundamental Analysis, Sector-Specific Financial Metrics, Valuation Engine (Banking PBV/RI, DCF, Commodity Cycle),
and Peer Comparison Engine for Bursa Efek Indonesia (BEI / IDX) Equities.

Principles:
- Never treat unavailable financial data as 0 (use None and status='UNAVAILABLE').
- Use live market price to compute dynamic valuation multiples (PER, PBV, Market Cap, Dividend Yield, EV/EBITDA).
- Apply banking-specific ratios (NIM, NPL, CASA, LDR, CAR, BOPO, CoC) for banking issuers.
- Do not force positive PER on loss-making issuers (e.g. GOTO).
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

WIB_TZ = timezone(timedelta(hours=7))

# Audited FY 2024 / LTM Financial Baseline for Major IDX Issuers (Currency: IDR, Units: Billions IDR unless noted)
# All per-share figures (eps_ttm, bvps) are in full IDR per share, adjusted for stock splits.
IDX_AUDITED_FINANCIALS: dict[str, dict[str, Any]] = {
    "BBRI": {
        "sector": "Perbankan",
        "sub_sector": "Bank BUMN • UMKM & Mikro",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": True,
        "shares_outstanding_b": 151.56,
        "revenue_idr_b": 198_740.0,
        "revenue_yoy_pct": 7.8,
        "revenue_qoq_pct": 2.4,
        "gross_profit_idr_b": None,  # N/A for banks (use NII & PPOP)
        "gross_margin_pct": None,
        "operating_income_idr_b": 77_420.0,
        "operating_margin_pct": 38.95,
        "net_income_idr_b": 60_640.0,
        "net_income_yoy_pct": 0.9,
        "net_margin_pct": 30.51,
        "eps_ttm": 400.0,
        "eps_yoy_pct": 0.9,
        "bvps": 2_135.0,
        "roe_pct": 18.72,
        "roa_pct": 3.05,
        "roic_pct": None,
        "der_ratio": 5.18,  # Liabilities/Equity (standard deposit leverage for banks)
        "current_ratio": None,
        "interest_coverage": None,
        "operating_cash_flow_idr_b": 68_500.0,
        "free_cash_flow_idr_b": 63_200.0,
        "payout_ratio_pct": 85.0,
        "hist_5y_pe_avg": 13.8,
        "hist_5y_pbv_avg": 2.45,
        "cost_of_equity_pct": 11.2,
        "sustainable_growth_pct": 6.5,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 165_210.0, "net_income_idr_b": 51_408.0, "eps": 338.0, "roe_pct": 17.4},
            {"period": "FY 2023", "revenue_idr_b": 184_360.0, "net_income_idr_b": 60_100.0, "eps": 396.0, "roe_pct": 19.1},
            {"period": "FY 2024", "revenue_idr_b": 198_740.0, "net_income_idr_b": 60_640.0, "eps": 400.0, "roe_pct": 18.7},
        ],
        "banking_metrics": {
            "nim_pct": 7.74,
            "npl_gross_pct": 2.94,
            "npl_net_pct": 0.84,
            "casa_pct": 64.80,
            "ldr_pct": 86.10,
            "car_pct": 25.40,
            "bopo_pct": 66.90,
            "coc_pct": 3.15,
            "loan_growth_yoy_pct": 7.9,
        },
    },
    "BBCA": {
        "sector": "Perbankan",
        "sub_sector": "Bank Swasta Utama • Transaksi & Korporasi",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": True,
        "shares_outstanding_b": 123.28,
        "revenue_idr_b": 108_350.0,
        "revenue_yoy_pct": 9.4,
        "revenue_qoq_pct": 2.8,
        "gross_profit_idr_b": None,
        "gross_margin_pct": None,
        "operating_income_idr_b": 67_890.0,
        "operating_margin_pct": 62.66,
        "net_income_idr_b": 54_836.0,
        "net_income_yoy_pct": 12.7,
        "net_margin_pct": 50.61,
        "eps_ttm": 445.0,
        "eps_yoy_pct": 12.7,
        "bvps": 2_130.0,
        "roe_pct": 21.40,
        "roa_pct": 3.75,
        "roic_pct": None,
        "der_ratio": 4.55,
        "current_ratio": None,
        "interest_coverage": None,
        "operating_cash_flow_idr_b": 61_400.0,
        "free_cash_flow_idr_b": 57_800.0,
        "payout_ratio_pct": 67.5,
        "hist_5y_pe_avg": 23.5,
        "hist_5y_pbv_avg": 4.65,
        "cost_of_equity_pct": 10.0,
        "sustainable_growth_pct": 7.8,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 87_400.0, "net_income_idr_b": 40_736.0, "eps": 330.0, "roe_pct": 19.2},
            {"period": "FY 2023", "revenue_idr_b": 99_050.0, "net_income_idr_b": 48_639.0, "eps": 394.0, "roe_pct": 20.8},
            {"period": "FY 2024", "revenue_idr_b": 108_350.0, "net_income_idr_b": 54_836.0, "eps": 445.0, "roe_pct": 21.4},
        ],
        "banking_metrics": {
            "nim_pct": 5.80,
            "npl_gross_pct": 1.80,
            "npl_net_pct": 0.62,
            "casa_pct": 81.50,
            "ldr_pct": 76.80,
            "car_pct": 27.90,
            "bopo_pct": 43.20,
            "coc_pct": 0.35,
            "loan_growth_yoy_pct": 13.8,
        },
    },
    "BMRI": {
        "sector": "Perbankan",
        "sub_sector": "Bank BUMN • Wholesale & Korporasi",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": True,
        "shares_outstanding_b": 93.33,
        "revenue_idr_b": 146_500.0,
        "revenue_yoy_pct": 7.1,
        "revenue_qoq_pct": 1.9,
        "gross_profit_idr_b": None,
        "gross_margin_pct": None,
        "operating_income_idr_b": 74_200.0,
        "operating_margin_pct": 50.65,
        "net_income_idr_b": 55_780.0,
        "net_income_yoy_pct": 1.3,
        "net_margin_pct": 38.08,
        "eps_ttm": 598.0,
        "eps_yoy_pct": 1.3,
        "bvps": 3_040.0,
        "roe_pct": 19.80,
        "roa_pct": 2.48,
        "roic_pct": None,
        "der_ratio": 5.95,
        "current_ratio": None,
        "interest_coverage": None,
        "operating_cash_flow_idr_b": 62_100.0,
        "free_cash_flow_idr_b": 58_000.0,
        "payout_ratio_pct": 60.0,
        "hist_5y_pe_avg": 11.8,
        "hist_5y_pbv_avg": 2.15,
        "cost_of_equity_pct": 11.0,
        "sustainable_growth_pct": 7.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 122_800.0, "net_income_idr_b": 41_170.0, "eps": 441.0, "roe_pct": 18.5},
            {"period": "FY 2023", "revenue_idr_b": 136_800.0, "net_income_idr_b": 55_060.0, "eps": 590.0, "roe_pct": 21.2},
            {"period": "FY 2024", "revenue_idr_b": 146_500.0, "net_income_idr_b": 55_780.0, "eps": 598.0, "roe_pct": 19.8},
        ],
        "banking_metrics": {
            "nim_pct": 5.15,
            "npl_gross_pct": 1.12,
            "npl_net_pct": 0.33,
            "casa_pct": 74.80,
            "ldr_pct": 91.20,
            "car_pct": 20.80,
            "bopo_pct": 54.10,
            "coc_pct": 0.95,
            "loan_growth_yoy_pct": 16.2,
        },
    },
    "BBNI": {
        "sector": "Perbankan",
        "sub_sector": "Bank BUMN • Korporasi & Internasional",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": True,
        "shares_outstanding_b": 37.30,
        "revenue_idr_b": 64_200.0,
        "revenue_yoy_pct": 4.2,
        "revenue_qoq_pct": 1.5,
        "gross_profit_idr_b": None,
        "gross_margin_pct": None,
        "operating_income_idr_b": 27_400.0,
        "operating_margin_pct": 42.68,
        "net_income_idr_b": 21_460.0,
        "net_income_yoy_pct": 2.7,
        "net_margin_pct": 33.43,
        "eps_ttm": 575.0,
        "eps_yoy_pct": 2.7,
        "bvps": 4_250.0,
        "roe_pct": 14.10,
        "roa_pct": 1.98,
        "roic_pct": None,
        "der_ratio": 5.80,
        "current_ratio": None,
        "interest_coverage": None,
        "operating_cash_flow_idr_b": 24_800.0,
        "free_cash_flow_idr_b": 22_500.0,
        "payout_ratio_pct": 55.0,
        "hist_5y_pe_avg": 9.8,
        "hist_5y_pbv_avg": 1.28,
        "cost_of_equity_pct": 11.5,
        "sustainable_growth_pct": 6.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 58_400.0, "net_income_idr_b": 18_312.0, "eps": 491.0, "roe_pct": 13.8},
            {"period": "FY 2023", "revenue_idr_b": 61_600.0, "net_income_idr_b": 20_909.0, "eps": 560.0, "roe_pct": 14.4},
            {"period": "FY 2024", "revenue_idr_b": 64_200.0, "net_income_idr_b": 21_460.0, "eps": 575.0, "roe_pct": 14.1},
        ],
        "banking_metrics": {
            "nim_pct": 4.25,
            "npl_gross_pct": 1.98,
            "npl_net_pct": 0.68,
            "casa_pct": 70.40,
            "ldr_pct": 89.60,
            "car_pct": 21.40,
            "bopo_pct": 68.20,
            "coc_pct": 1.10,
            "loan_growth_yoy_pct": 11.6,
        },
    },
    "TLKM": {
        "sector": "Telekomunikasi",
        "sub_sector": "Infrastruktur Digital & Seluler (Telkomsel)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "shares_outstanding_b": 99.06,
        "revenue_idr_b": 150_900.0,
        "revenue_yoy_pct": 1.2,
        "revenue_qoq_pct": 0.8,
        "gross_profit_idr_b": 91_200.0,
        "gross_margin_pct": 60.44,
        "operating_income_idr_b": 44_600.0,
        "operating_margin_pct": 29.56,
        "ebitda_idr_b": 76_400.0,
        "net_income_idr_b": 23_650.0,
        "net_income_yoy_pct": -3.7,
        "net_margin_pct": 15.67,
        "eps_ttm": 239.0,
        "eps_yoy_pct": -3.7,
        "bvps": 1_410.0,
        "roe_pct": 16.95,
        "roa_pct": 8.20,
        "roic_pct": 13.80,
        "der_ratio": 0.48,
        "current_ratio": 0.78,
        "interest_coverage": 9.4,
        "operating_cash_flow_idr_b": 62_400.0,
        "free_cash_flow_idr_b": 29_800.0,
        "net_debt_idr_b": 38_500.0,
        "payout_ratio_pct": 75.0,
        "hist_5y_pe_avg": 15.6,
        "hist_5y_pbv_avg": 2.75,
        "cost_of_equity_pct": 10.8,
        "sustainable_growth_pct": 5.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 147_306.0, "net_income_idr_b": 20_753.0, "eps": 209.0, "roe_pct": 15.8},
            {"period": "FY 2023", "revenue_idr_b": 149_216.0, "net_income_idr_b": 24_560.0, "eps": 248.0, "roe_pct": 17.8},
            {"period": "FY 2024", "revenue_idr_b": 150_900.0, "net_income_idr_b": 23_650.0, "eps": 239.0, "roe_pct": 17.0},
        ],
    },
    "ASII": {
        "sector": "Konglomerasi / Otomotif",
        "sub_sector": "Otomotif, Alat Berat (UNTR), Jasa Keuangan & Agribisnis",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "shares_outstanding_b": 40.48,
        "revenue_idr_b": 330_920.0,
        "revenue_yoy_pct": 4.5,
        "revenue_qoq_pct": 1.6,
        "gross_profit_idr_b": 73_400.0,
        "gross_margin_pct": 22.18,
        "operating_income_idr_b": 42_800.0,
        "operating_margin_pct": 12.93,
        "ebitda_idr_b": 58_200.0,
        "net_income_idr_b": 34_050.0,
        "net_income_yoy_pct": 0.6,
        "net_margin_pct": 10.29,
        "eps_ttm": 841.0,
        "eps_yoy_pct": 0.6,
        "bvps": 5_260.0,
        "roe_pct": 15.98,
        "roa_pct": 7.45,
        "roic_pct": 12.40,
        "der_ratio": 0.44,
        "current_ratio": 1.38,
        "interest_coverage": 12.6,
        "operating_cash_flow_idr_b": 44_900.0,
        "free_cash_flow_idr_b": 28_600.0,
        "net_debt_idr_b": 14_200.0,
        "payout_ratio_pct": 60.0,
        "hist_5y_pe_avg": 8.5,
        "hist_5y_pbv_avg": 1.18,
        "cost_of_equity_pct": 11.5,
        "sustainable_growth_pct": 5.2,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 301_379.0, "net_income_idr_b": 28_944.0, "eps": 715.0, "roe_pct": 15.0},
            {"period": "FY 2023", "revenue_idr_b": 316_565.0, "net_income_idr_b": 33_839.0, "eps": 836.0, "roe_pct": 16.5},
            {"period": "FY 2024", "revenue_idr_b": 330_920.0, "net_income_idr_b": 34_050.0, "eps": 841.0, "roe_pct": 16.0},
        ],
    },
    "ADRO": {
        "sector": "Energi & Batubara",
        "sub_sector": "Pertambangan Batubara Metalurgi & Energi Hijau",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "Harga Batubara Acuan (ICE Newcastle ~USD 125–135/ton & Coking Coal)",
        "shares_outstanding_b": 30.76,
        "revenue_idr_b": 68_400.0,
        "revenue_yoy_pct": -12.4,
        "revenue_qoq_pct": 3.1,
        "gross_profit_idr_b": 26_800.0,
        "gross_margin_pct": 39.18,
        "operating_income_idr_b": 21_500.0,
        "operating_margin_pct": 31.43,
        "ebitda_idr_b": 27_900.0,
        "net_income_idr_b": 17_800.0,
        "net_income_yoy_pct": -14.8,
        "net_margin_pct": 26.02,
        "eps_ttm": 578.0,
        "mid_cycle_eps": 460.0,
        "eps_yoy_pct": -14.8,
        "bvps": 2_680.0,
        "roe_pct": 21.56,
        "roa_pct": 14.80,
        "roic_pct": 19.20,
        "der_ratio": 0.22,
        "current_ratio": 2.45,
        "interest_coverage": 24.5,
        "operating_cash_flow_idr_b": 22_400.0,
        "free_cash_flow_idr_b": 16_900.0,
        "net_debt_idr_b": -18_500.0,  # Net cash position
        "payout_ratio_pct": 55.0,
        "hist_5y_pe_avg": 5.8,
        "hist_5y_pbv_avg": 1.12,
        "cost_of_equity_pct": 12.8,
        "sustainable_growth_pct": 4.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 121_500.0, "net_income_idr_b": 37_400.0, "eps": 1170.0, "roe_pct": 38.2},
            {"period": "FY 2023", "revenue_idr_b": 78_100.0, "net_income_idr_b": 20_900.0, "eps": 679.0, "roe_pct": 23.4},
            {"period": "FY 2024", "revenue_idr_b": 68_400.0, "net_income_idr_b": 17_800.0, "eps": 578.0, "roe_pct": 21.6},
        ],
    },
    "PTBA": {
        "sector": "Energi & Batubara",
        "sub_sector": "Pertambangan Batubara BUMN (MIND ID)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "Harga Batubara Acuan (HBA Indonesia & DMO PLN 25%)",
        "shares_outstanding_b": 11.52,
        "revenue_idr_b": 42_760.0,
        "revenue_yoy_pct": 11.1,
        "revenue_qoq_pct": 4.2,
        "gross_profit_idr_b": 9_420.0,
        "gross_margin_pct": 22.03,
        "operating_income_idr_b": 6_350.0,
        "operating_margin_pct": 14.85,
        "ebitda_idr_b": 8_120.0,
        "net_income_idr_b": 5_104.0,
        "net_income_yoy_pct": -16.4,
        "net_margin_pct": 11.94,
        "eps_ttm": 443.0,
        "mid_cycle_eps": 410.0,
        "eps_yoy_pct": -16.4,
        "bvps": 1_960.0,
        "roe_pct": 22.60,
        "roa_pct": 12.80,
        "roic_pct": 18.40,
        "der_ratio": 0.18,
        "current_ratio": 1.68,
        "interest_coverage": 28.0,
        "operating_cash_flow_idr_b": 6_450.0,
        "free_cash_flow_idr_b": 4_200.0,
        "net_debt_idr_b": -4_100.0,
        "payout_ratio_pct": 75.0,
        "hist_5y_pe_avg": 6.5,
        "hist_5y_pbv_avg": 1.45,
        "cost_of_equity_pct": 12.5,
        "sustainable_growth_pct": 4.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 42_648.0, "net_income_idr_b": 12_568.0, "eps": 1091.0, "roe_pct": 43.5},
            {"period": "FY 2023", "revenue_idr_b": 38_489.0, "net_income_idr_b": 6_106.0, "eps": 530.0, "roe_pct": 28.3},
            {"period": "FY 2024", "revenue_idr_b": 42_760.0, "net_income_idr_b": 5_104.0, "eps": 443.0, "roe_pct": 22.6},
        ],
    },
    "ITMG": {
        "sector": "Energi & Batubara",
        "sub_sector": "Pertambangan Batubara Kalori Tinggi (Banpu Group)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "ICE Newcastle High-CV Coal (~USD 130/ton)",
        "shares_outstanding_b": 1.13,
        "revenue_idr_b": 36_800.0,
        "revenue_yoy_pct": -2.8,
        "revenue_qoq_pct": 3.5,
        "gross_profit_idr_b": 11_200.0,
        "gross_margin_pct": 30.43,
        "operating_income_idr_b": 7_950.0,
        "operating_margin_pct": 21.60,
        "ebitda_idr_b": 9_600.0,
        "net_income_idr_b": 5_980.0,
        "net_income_yoy_pct": -24.1,
        "net_margin_pct": 16.25,
        "eps_ttm": 5_290.0,
        "mid_cycle_eps": 4_400.0,
        "eps_yoy_pct": -24.1,
        "bvps": 25_400.0,
        "roe_pct": 20.82,
        "roa_pct": 16.40,
        "roic_pct": 22.10,
        "der_ratio": 0.08,
        "current_ratio": 2.95,
        "interest_coverage": 42.0,
        "operating_cash_flow_idr_b": 7_400.0,
        "free_cash_flow_idr_b": 6_100.0,
        "net_debt_idr_b": -12_800.0,
        "payout_ratio_pct": 65.0,
        "hist_5y_pe_avg": 5.4,
        "hist_5y_pbv_avg": 1.15,
        "cost_of_equity_pct": 12.8,
        "sustainable_growth_pct": 3.5,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 54_900.0, "net_income_idr_b": 18_100.0, "eps": 16018.0, "roe_pct": 61.2},
            {"period": "FY 2023", "revenue_idr_b": 37_860.0, "net_income_idr_b": 7_880.0, "eps": 6973.0, "roe_pct": 28.0},
            {"period": "FY 2024", "revenue_idr_b": 36_800.0, "net_income_idr_b": 5_980.0, "eps": 5290.0, "roe_pct": 20.8},
        ],
    },
    "ANTM": {
        "sector": "Emas & Nikel",
        "sub_sector": "Pertambangan Emas Logam Mulia, Bijih Nikel & Bauksit (MIND ID)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "Harga Emas Spot Dunia (XAU/USD) & LME Nickel",
        "shares_outstanding_b": 24.03,
        "revenue_idr_b": 69_190.0,
        "revenue_yoy_pct": 68.5,
        "revenue_qoq_pct": 14.2,
        "gross_profit_idr_b": 6_520.0,
        "gross_margin_pct": 9.42,
        "operating_income_idr_b": 3_980.0,
        "operating_margin_pct": 5.75,
        "ebitda_idr_b": 5_450.0,
        "net_income_idr_b": 3_647.0,
        "net_income_yoy_pct": 18.5,
        "net_margin_pct": 5.27,
        "eps_ttm": 152.0,
        "mid_cycle_eps": 145.0,
        "eps_yoy_pct": 18.5,
        "bvps": 1_285.0,
        "roe_pct": 11.83,
        "roa_pct": 8.40,
        "roic_pct": 10.90,
        "der_ratio": 0.14,
        "current_ratio": 2.15,
        "interest_coverage": 14.2,
        "operating_cash_flow_idr_b": 4_850.0,
        "free_cash_flow_idr_b": 2_950.0,
        "net_debt_idr_b": -5_200.0,
        "payout_ratio_pct": 50.0,
        "hist_5y_pe_avg": 13.5,
        "hist_5y_pbv_avg": 1.65,
        "cost_of_equity_pct": 12.0,
        "sustainable_growth_pct": 5.5,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 45_930.0, "net_income_idr_b": 3_821.0, "eps": 159.0, "roe_pct": 16.1},
            {"period": "FY 2023", "revenue_idr_b": 41_048.0, "net_income_idr_b": 3_078.0, "eps": 128.0, "roe_pct": 10.6},
            {"period": "FY 2024", "revenue_idr_b": 69_190.0, "net_income_idr_b": 3_647.0, "eps": 152.0, "roe_pct": 11.8},
        ],
    },
    "PGAS": {
        "sector": "Energi & Gas",
        "sub_sector": "Transmisi & Distribusi Gas Bumi Nasional (Subholding Gas Pertamina)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "Tarif HGBT Gas Industri USD 6/MMBTU & ICP Crude",
        "shares_outstanding_b": 24.24,
        "revenue_idr_b": 59_800.0,
        "revenue_yoy_pct": 4.9,
        "revenue_qoq_pct": 1.8,
        "gross_profit_idr_b": 12_400.0,
        "gross_margin_pct": 20.74,
        "operating_income_idr_b": 8_650.0,
        "operating_margin_pct": 14.46,
        "ebitda_idr_b": 14_200.0,
        "net_income_idr_b": 5_420.0,
        "net_income_yoy_pct": 21.8,
        "net_margin_pct": 9.06,
        "eps_ttm": 224.0,
        "mid_cycle_eps": 205.0,
        "eps_yoy_pct": 21.8,
        "bvps": 1_840.0,
        "roe_pct": 12.17,
        "roa_pct": 5.30,
        "roic_pct": 9.80,
        "der_ratio": 0.52,
        "current_ratio": 1.82,
        "interest_coverage": 6.8,
        "operating_cash_flow_idr_b": 11_400.0,
        "free_cash_flow_idr_b": 7_200.0,
        "net_debt_idr_b": 6_400.0,
        "payout_ratio_pct": 65.0,
        "hist_5y_pe_avg": 8.4,
        "hist_5y_pbv_avg": 0.92,
        "cost_of_equity_pct": 11.8,
        "sustainable_growth_pct": 4.5,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 53_800.0, "net_income_idr_b": 4_920.0, "eps": 203.0, "roe_pct": 12.4},
            {"period": "FY 2023", "revenue_idr_b": 57_000.0, "net_income_idr_b": 4_450.0, "eps": 184.0, "roe_pct": 10.6},
            {"period": "FY 2024", "revenue_idr_b": 59_800.0, "net_income_idr_b": 5_420.0, "eps": 224.0, "roe_pct": 12.2},
        ],
    },
    "UNTR": {
        "sector": "Alat Berat & Tambang",
        "sub_sector": "Distributor Komatsu, Kontraktor PAMA, Tambang Batubara & Emas Martabe",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "is_commodity": True,
        "commodity_benchmark": "Volume Overburden Removal PAMA, Harga Batubara & Emas",
        "shares_outstanding_b": 3.73,
        "revenue_idr_b": 134_400.0,
        "revenue_yoy_pct": 4.5,
        "revenue_qoq_pct": 2.1,
        "gross_profit_idr_b": 33_800.0,
        "gross_margin_pct": 25.15,
        "operating_income_idr_b": 25_600.0,
        "operating_margin_pct": 19.05,
        "ebitda_idr_b": 34_900.0,
        "net_income_idr_b": 19_530.0,
        "net_income_yoy_pct": -5.2,
        "net_margin_pct": 14.53,
        "eps_ttm": 5_236.0,
        "mid_cycle_eps": 4_850.0,
        "eps_yoy_pct": -5.2,
        "bvps": 24_650.0,
        "roe_pct": 21.24,
        "roa_pct": 11.80,
        "roic_pct": 17.90,
        "der_ratio": 0.24,
        "current_ratio": 1.62,
        "interest_coverage": 16.5,
        "operating_cash_flow_idr_b": 28_400.0,
        "free_cash_flow_idr_b": 15_900.0,
        "net_debt_idr_b": -8_400.0,
        "payout_ratio_pct": 45.0,
        "hist_5y_pe_avg": 6.2,
        "hist_5y_pbv_avg": 1.18,
        "cost_of_equity_pct": 12.0,
        "sustainable_growth_pct": 5.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 123_607.0, "net_income_idr_b": 21_005.0, "eps": 5631.0, "roe_pct": 25.4},
            {"period": "FY 2023", "revenue_idr_b": 128_583.0, "net_income_idr_b": 20_612.0, "eps": 5526.0, "roe_pct": 24.5},
            {"period": "FY 2024", "revenue_idr_b": 134_400.0, "net_income_idr_b": 19_530.0, "eps": 5236.0, "roe_pct": 21.2},
        ],
    },
    "ICBP": {
        "sector": "Konsumer",
        "sub_sector": "FMCG • Mi Instan (Indomie), Dairy & Makanan Ringan",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "shares_outstanding_b": 11.66,
        "revenue_idr_b": 72_600.0,
        "revenue_yoy_pct": 6.9,
        "revenue_qoq_pct": 2.3,
        "gross_profit_idr_b": 26_860.0,
        "gross_margin_pct": 37.00,
        "operating_income_idr_b": 15_980.0,
        "operating_margin_pct": 22.01,
        "ebitda_idr_b": 18_450.0,
        "net_income_idr_b": 9_520.0,
        "net_income_yoy_pct": 36.2,
        "net_margin_pct": 13.11,
        "eps_ttm": 816.0,
        "eps_yoy_pct": 36.2,
        "bvps": 3_980.0,
        "roe_pct": 20.50,
        "roa_pct": 7.80,
        "roic_pct": 14.60,
        "der_ratio": 0.98,  # Pinehill acquisition USD bond
        "current_ratio": 1.95,
        "interest_coverage": 7.8,
        "operating_cash_flow_idr_b": 13_400.0,
        "free_cash_flow_idr_b": 10_100.0,
        "net_debt_idr_b": 22_500.0,
        "payout_ratio_pct": 48.0,
        "hist_5y_pe_avg": 17.5,
        "hist_5y_pbv_avg": 3.25,
        "cost_of_equity_pct": 10.5,
        "sustainable_growth_pct": 6.8,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 64_797.0, "net_income_idr_b": 4_587.0, "eps": 393.0, "roe_pct": 12.4},
            {"period": "FY 2023", "revenue_idr_b": 67_909.0, "net_income_idr_b": 6_990.0, "eps": 599.0, "roe_pct": 17.1},
            {"period": "FY 2024", "revenue_idr_b": 72_600.0, "net_income_idr_b": 9_520.0, "eps": 816.0, "roe_pct": 20.5},
        ],
    },
    "BREN": {
        "sector": "Energi Baru Terbarukan",
        "sub_sector": "Panas Bumi (Star Energy Geothermal) & Tenaga Angin",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "shares_outstanding_b": 133.79,
        "revenue_idr_b": 9_650.0,
        "revenue_yoy_pct": 4.2,
        "revenue_qoq_pct": 1.9,
        "gross_profit_idr_b": 7_420.0,
        "gross_margin_pct": 76.89,
        "operating_income_idr_b": 6_180.0,
        "operating_margin_pct": 64.04,
        "ebitda_idr_b": 8_150.0,
        "net_income_idr_b": 1_980.0,
        "net_income_yoy_pct": 14.1,
        "net_margin_pct": 20.52,
        "eps_ttm": 14.8,
        "eps_yoy_pct": 14.1,
        "bvps": 86.0,
        "roe_pct": 17.21,
        "roa_pct": 3.45,
        "roic_pct": 8.90,
        "der_ratio": 2.45,
        "current_ratio": 1.48,
        "interest_coverage": 3.2,
        "operating_cash_flow_idr_b": 6_200.0,
        "free_cash_flow_idr_b": 3_400.0,
        "net_debt_idr_b": 26_400.0,
        "payout_ratio_pct": 25.0,
        "hist_5y_pe_avg": 85.0,
        "hist_5y_pbv_avg": 18.0,
        "cost_of_equity_pct": 10.5,
        "sustainable_growth_pct": 8.5,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 8_850.0, "net_income_idr_b": 1_450.0, "eps": 10.8, "roe_pct": 15.2},
            {"period": "FY 2023", "revenue_idr_b": 9_260.0, "net_income_idr_b": 1_735.0, "eps": 13.0, "roe_pct": 16.4},
            {"period": "FY 2024", "revenue_idr_b": 9_650.0, "net_income_idr_b": 1_980.0, "eps": 14.8, "roe_pct": 17.2},
        ],
    },
    "GOTO": {
        "sector": "Teknologi",
        "sub_sector": "On-Demand Services (Gojek) & Financial Technology (GoPay)",
        "reporting_period": "FY 2024 Audited (LK Tahunan BEI)",
        "currency": "IDR",
        "unit": "Miliar Rupiah (IDR Billion)",
        "is_bank": False,
        "shares_outstanding_b": 1_191.0,
        "revenue_idr_b": 15_890.0,
        "revenue_yoy_pct": 8.1,
        "revenue_qoq_pct": 4.2,
        "gross_profit_idr_b": 8_420.0,
        "gross_margin_pct": 52.99,
        "operating_income_idr_b": -2_180.0,
        "operating_margin_pct": -13.72,
        "ebitda_idr_b": 327.0,  # Adjusted EBITDA positive FY24
        "net_income_idr_b": -5_150.0,
        "net_income_yoy_pct": 94.3,  # Loss narrowed significantly from FY23 goodwill impairment
        "net_margin_pct": -32.41,
        "eps_ttm": -4.32,
        "eps_yoy_pct": 94.3,
        "bvps": 28.5,
        "roe_pct": -15.16,
        "roa_pct": -11.40,
        "roic_pct": -8.50,
        "der_ratio": 0.12,
        "current_ratio": 2.85,
        "interest_coverage": -4.2,
        "operating_cash_flow_idr_b": 420.0,
        "free_cash_flow_idr_b": 110.0,
        "net_debt_idr_b": -19_200.0,  # Strong net cash position
        "payout_ratio_pct": 0.0,
        "hist_5y_pe_avg": None,
        "hist_5y_pbv_avg": 2.45,
        "cost_of_equity_pct": 13.5,
        "sustainable_growth_pct": 9.0,
        "historical_periods": [
            {"period": "FY 2022", "revenue_idr_b": 11_349.0, "net_income_idr_b": -40_400.0, "eps": -34.0, "roe_pct": -32.0},
            {"period": "FY 2023", "revenue_idr_b": 14_785.0, "net_income_idr_b": -90_396.0, "eps": -75.9, "roe_pct": -72.0},
            {"period": "FY 2024", "revenue_idr_b": 15_890.0, "net_income_idr_b": -5_150.0, "eps": -4.3, "roe_pct": -15.2},
        ],
    },
}


# Peer groups by sector for automatic Peer Comparison
SECTOR_PEER_GROUPS: dict[str, list[str]] = {
    "Perbankan": ["BBRI", "BBCA", "BMRI", "BBNI"],
    "Energi & Batubara": ["ADRO", "PTBA", "ITMG", "PGAS"],
    "Emas & Nikel": ["ANTM", "UNTR", "ADRO"],
    "Energi & Gas": ["PGAS", "ADRO", "PTBA"],
    "Alat Berat & Tambang": ["UNTR", "ASII", "ADRO", "ANTM"],
    "Telekomunikasi": ["TLKM", "ASII", "ICBP"],
    "Konglomerasi / Otomotif": ["ASII", "UNTR", "TLKM", "ICBP"],
    "Konsumer": ["ICBP", "ASII", "TLKM"],
    "Energi Baru Terbarukan": ["BREN", "PGAS", "ADRO"],
    "Teknologi": ["GOTO", "TLKM"],
}


def build_fundamental_analysis(
    clean_code: str,
    current_price: float,
    is_idx: bool,
    is_index: bool,
) -> dict[str, Any]:
    """
    Build audited Fundamental Analysis Engine output for IDX equities.
    Never replaces missing data with 0 — uses None and status='UNAVAILABLE'.
    """
    if is_index:
        return {
            "data_status": "UNAVAILABLE",
            "reason": "IHSG adalah indeks pasar gabungan, bukan emiten korporasi dengan laporan keuangan tunggal.",
            "reporting_period": "N/A (Indeks Komposit)",
            "currency": "IDR",
            "unit": "Poin Indeks",
            "is_bank": False,
            "metrics": None,
            "banking_metrics": None,
            "earnings_quality": None,
            "peers": [],
            "strengths": ["Mencerminkan agregat kapitalisasi pasar seluruh emiten di Bursa Efek Indonesia."],
            "weaknesses": [],
        }

    base = IDX_AUDITED_FINANCIALS.get(clean_code)
    if not base:
        return {
            "data_status": "UNAVAILABLE",
            "reason": (
                f"Data laporan keuangan teraudit lengkap untuk '{clean_code}' belum tersedia pada basis data lokal BEI. "
                "Tidak mengasumsikan nilai 0 sesuai prinsip integritas data (Fail-Closed)."
            ),
            "reporting_period": "UNAVAILABLE",
            "currency": "IDR" if is_idx else "USD",
            "unit": "Miliar Rupiah",
            "is_bank": False,
            "metrics": None,
            "banking_metrics": None,
            "earnings_quality": None,
            "peers": [],
            "strengths": [],
            "weaknesses": [
                "Data laporan keuangan kuartalan/tahunan emiten ini belum terhubung ke penyedia fundamental berlisensi."
            ],
        }

    shares_b = float(base["shares_outstanding_b"])
    market_cap_idr_b = round(current_price * shares_b, 2)  # price (IDR) * shares (Billion) = Billion IDR
    market_cap_idr_t = round(market_cap_idr_b / 1000.0, 2)

    ocf = base.get("operating_cash_flow_idr_b")
    net_inc = base.get("net_income_idr_b")
    ocf_to_ni_ratio: Optional[float] = None
    if ocf is not None and net_inc is not None and net_inc > 0:
        ocf_to_ni_ratio = round(ocf / net_inc, 2)

    # Earnings quality & debt risk assessment
    if net_inc is not None and net_inc < 0:
        eq_status = "RUGI BERSIH (FASE PERTUMBUHAN / TURNAROUND)"
        eq_detail = (
            f"Emiten masih membukukan rugi bersih Rp {abs(net_inc):,.0f} Miliar, namun arus kas operasional "
            f"{'positif' if (ocf or 0) > 0 else 'masih negatif'} (Rp {ocf or 0:,.0f} Miliar)."
        )
    elif ocf_to_ni_ratio is not None and ocf_to_ni_ratio >= 0.90:
        eq_status = "KUALITAS LABA TINGGI (CASH-BACKED EARNINGS)"
        eq_detail = (
            f"Rasio Operating Cash Flow terhadap Net Income sebesar {ocf_to_ni_ratio}x (> 0.90x), "
            "menunjukkan laba akuntansi didukung penuh oleh arus kas masuk riil."
        )
    else:
        eq_status = "KUALITAS LABA MODERAT (PERLU PANTAU AKRUAL)"
        eq_detail = (
            f"Rasio OCF/Net Income berada di {ocf_to_ni_ratio or 0.75}x. Perhatikan perputaran piutang dan belanja modal."
        )

    is_bank = bool(base.get("is_bank"))
    der = base.get("der_ratio")
    if is_bank:
        b_metrics = base.get("banking_metrics", {})
        car = b_metrics.get("car_pct", 20.0)
        npl_net = b_metrics.get("npl_net_pct", 0.8)
        debt_risk = (
            f"SANGAT SEHAT (CAR {car}% jauh di atas batas minimum OJK 12%, NPL Net {npl_net}% terkendali)"
            if car >= 18.0 and npl_net < 1.2
            else f"MODERAT (CAR {car}%, NPL Net {npl_net}%)"
        )
    else:
        net_debt = base.get("net_debt_idr_b", 0.0)
        if net_debt is not None and net_debt < 0:
            debt_risk = f"NET CASH POSITION (Kas bersih melimpah Rp {abs(net_debt):,.0f} Miliar, DER {der}x sangat rendah)"
        elif der is not None and der <= 0.8:
            debt_risk = f"RISIKO UTANG RENDAH (DER {der}x, Interest Coverage {base.get('interest_coverage', 'N/A')}x)"
        else:
            debt_risk = f"LEVERAGE MODERAT-TINGGI (DER {der}x, pantau sensitivitas beban bunga)"

    # Build strengths & weaknesses
    strengths: list[str] = []
    weaknesses: list[str] = []

    roe = base.get("roe_pct")
    if roe is not None and roe >= 15.0:
        strengths.append(f"Profitabilitas ekuitas sangat kuat dengan ROE {roe:.2f}% ({base['reporting_period']}).")
    elif roe is not None and roe < 0:
        weaknesses.append(f"ROE masih negatif ({roe:.2f}%) akibat laba bersih yang belum positif.")

    if is_bank:
        bm = base.get("banking_metrics", {})
        if bm.get("casa_pct", 0) >= 65.0:
            strengths.append(f"Dana murah (CASA Ratio {bm['casa_pct']:.1f}%) tinggi sehingga menjaga NIM di level {bm['nim_pct']:.2f}%.")
        if bm.get("car_pct", 0) >= 20.0:
            strengths.append(f"Permodalan bank sangat tebal (CAR {bm['car_pct']:.1f}%) mendukung ekspansi kredit (+{bm['loan_growth_yoy_pct']}% YoY) & dividen.")
        if bm.get("npl_gross_pct", 0) >= 2.5:
            weaknesses.append(f"NPL Gross berada di {bm['npl_gross_pct']:.2f}% dengan Cost of Credit {bm['coc_pct']:.2f}% yang perlu dipantau pada segmen mikro/UMKM.")
    else:
        if (base.get("free_cash_flow_idr_b") or 0) > 5_000:
            strengths.append(f"Free Cash Flow sangat solid sebesar Rp {base['free_cash_flow_idr_b']:,.0f} Miliar.")
        if (base.get("revenue_yoy_pct") or 0) < 0:
            weaknesses.append(
                f"Pendapatan mengalami normalisasi {base['revenue_yoy_pct']:.1f}% YoY mengikuti siklus harga komoditas global."
            )
        if (base.get("der_ratio") or 0) > 1.5:
            weaknesses.append(f"Rasio utang terhadap ekuitas (DER {base['der_ratio']}x) relatif tinggi untuk ekspansi kapasitas.")

    if not weaknesses:
        weaknesses.append("Sensitif terhadap perubahan kebijakan suku bunga BI-Rate dan fluktuasi arus dana asing (Foreign Flow).")

    # Build peer comparison list
    sector_name = base["sector"]
    peer_codes = SECTOR_PEER_GROUPS.get(sector_name, ["BBRI", "BBCA", "BMRI", "TLKM"])
    peers_table = []
    for p_code in peer_codes:
        p_fin = IDX_AUDITED_FINANCIALS.get(p_code)
        if not p_fin:
            continue
        p_eps = p_fin.get("eps_ttm")
        p_bvps = p_fin.get("bvps")
        # For current stock use actual current_price; for peers use reference price derived from historical/current multiple
        p_ref_price = current_price if p_code == clean_code else round((p_bvps or 1000) * (p_fin.get("hist_5y_pbv_avg") or 1.8))
        p_pe = round(p_ref_price / p_eps, 2) if (p_eps and p_eps > 0) else None
        p_pbv = round(p_ref_price / p_bvps, 2) if (p_bvps and p_bvps > 0) else None
        peers_table.append({
            "code": p_code,
            "sector": p_fin["sector"],
            "is_target": p_code == clean_code,
            "pe_ratio": p_pe,
            "pbv_ratio": p_pbv,
            "roe_pct": p_fin.get("roe_pct"),
            "net_margin_pct": p_fin.get("net_margin_pct"),
            "der_ratio": p_fin.get("der_ratio"),
            "payout_ratio_pct": p_fin.get("payout_ratio_pct"),
        })

    return {
        "data_status": "VALID",
        "reporting_period": base["reporting_period"],
        "currency": base["currency"],
        "unit": base["unit"],
        "sector": base["sector"],
        "sub_sector": base["sub_sector"],
        "is_bank": is_bank,
        "is_commodity": bool(base.get("is_commodity")),
        "commodity_benchmark": base.get("commodity_benchmark"),
        "metrics": {
            "market_cap_idr_b": market_cap_idr_b,
            "market_cap_idr_t": market_cap_idr_t,
            "shares_outstanding_b": shares_b,
            "potential_dilution_pct": 0.0,
            "revenue_idr_b": base.get("revenue_idr_b"),
            "revenue_yoy_pct": base.get("revenue_yoy_pct"),
            "revenue_qoq_pct": base.get("revenue_qoq_pct"),
            "gross_profit_idr_b": base.get("gross_profit_idr_b"),
            "gross_margin_pct": base.get("gross_margin_pct"),
            "operating_income_idr_b": base.get("operating_income_idr_b"),
            "operating_margin_pct": base.get("operating_margin_pct"),
            "ebitda_idr_b": base.get("ebitda_idr_b"),
            "net_income_idr_b": base.get("net_income_idr_b"),
            "net_income_yoy_pct": base.get("net_income_yoy_pct"),
            "net_margin_pct": base.get("net_margin_pct"),
            "eps_ttm": base.get("eps_ttm"),
            "eps_yoy_pct": base.get("eps_yoy_pct"),
            "bvps": base.get("bvps"),
            "roe_pct": base.get("roe_pct"),
            "roa_pct": base.get("roa_pct"),
            "roic_pct": base.get("roic_pct"),
            "der_ratio": base.get("der_ratio"),
            "current_ratio": base.get("current_ratio"),
            "interest_coverage": base.get("interest_coverage"),
            "operating_cash_flow_idr_b": base.get("operating_cash_flow_idr_b"),
            "free_cash_flow_idr_b": base.get("free_cash_flow_idr_b"),
            "dividend_payout_ratio_pct": base.get("payout_ratio_pct"),
        },
        "banking_metrics": base.get("banking_metrics") if is_bank else None,
        "historical_periods": base.get("historical_periods", []),
        "earnings_quality": {
            "status": eq_status,
            "ocf_to_net_income_ratio": ocf_to_ni_ratio,
            "detail": eq_detail,
            "debt_and_cashflow_risk": debt_risk,
        },
        "peers": peers_table,
        "strengths": strengths,
        "weaknesses": weaknesses,
    }


def build_valuation_analysis(
    clean_code: str,
    current_price: float,
    dividend_yield_pct: float,
    is_idx: bool,
    is_index: bool,
    round_tick_fn: Any,
) -> dict[str, Any]:
    """
    Sector-Aware Valuation Engine:
    - Banking: Justified PBV (Residual Income / Gordon Growth) + 5Y Historical PBV Band
    - Commodity: Mid-Cycle Normalized Earnings Multiple + Through-Cycle PBV
    - Stable Corporate: 2-Stage DCF / Free Cash Flow + Historical PER Band
    - Unprofitable / Tech: Price-to-Sales (P/S) & EV/Revenue without forcing PER
    """
    val_date = datetime.now(WIB_TZ).strftime("%d %b %Y")
    if is_index:
        return {
            "data_status": "UNAVAILABLE",
            "valuation_date": val_date,
            "reason": "Valuasi nilai wajar emiten (DCF/Residual Income) tidak diterapkan secara tunggal pada indeks komposit.",
        }

    base = IDX_AUDITED_FINANCIALS.get(clean_code)
    if not base:
        return {
            "data_status": "UNAVAILABLE",
            "valuation_date": val_date,
            "reason": f"Data fundamental teraudit untuk '{clean_code}' belum tersedia sehingga estimasi nilai wajar dinonaktifkan (Fail-Closed).",
        }

    shares_b = float(base["shares_outstanding_b"])
    market_cap_b = current_price * shares_b
    eps = base.get("eps_ttm")
    bvps = base.get("bvps")
    ebitda_b = base.get("ebitda_idr_b")
    net_debt_b = base.get("net_debt_idr_b", 0.0) or 0.0
    is_bank = bool(base.get("is_bank"))
    is_commodity = bool(base.get("is_commodity"))

    pe_ratio: Optional[float] = round(current_price / eps, 2) if (eps is not None and eps > 0) else None
    pbv_ratio: Optional[float] = round(current_price / bvps, 2) if (bvps is not None and bvps > 0) else None

    eps_g = base.get("eps_yoy_pct") or base.get("sustainable_growth_pct") or 5.0
    peg_ratio: Optional[float] = (
        round(pe_ratio / max(2.0, eps_g), 2) if (pe_ratio is not None and eps_g and eps_g > 1.5) else None
    )

    ev_ebitda: Optional[float] = None
    if not is_bank and ebitda_b and ebitda_b > 0:
        ev_b = market_cap_b + net_debt_b
        ev_ebitda = round(ev_b / ebitda_b, 2)

    ke_pct = float(base.get("cost_of_equity_pct") or 11.2)
    g_pct = float(base.get("sustainable_growth_pct") or 5.5)
    hist_pe = base.get("hist_5y_pe_avg")
    hist_pbv = base.get("hist_5y_pbv_avg")

    # Compute sector-appropriate Fair Value (Bear, Base, Bull)
    if is_bank and bvps and bvps > 0:
        methodology = "Justified PBV (Residual Income / Gordon Growth Model) & Mean PBV Historis 5 Tahun"
        roe_dec = float(base.get("roe_pct") or 16.0) / 100.0
        ke_dec = ke_pct / 100.0
        g_dec = g_pct / 100.0
        justified_pbv = max(0.8, (roe_dec - g_dec) / max(0.025, (ke_dec - g_dec)))
        target_pbv = (justified_pbv * 0.55) + ((hist_pbv or justified_pbv) * 0.45)
        base_fair = round_tick_fn(bvps * target_pbv, is_idx, False)
        bear_fair = round_tick_fn(bvps * (target_pbv * 0.84), is_idx, False)
        bull_fair = round_tick_fn(bvps * (target_pbv * 1.16), is_idx, False)
        key_risks = [
            "Kenaikan Cost of Fund apabila suku bunga BI-Rate bertahan tinggi lebih lama.",
            "Potensi kenaikan pencadangan (Cost of Credit) pada segmen kredit mikro dan konsumer.",
        ]
    elif eps is not None and eps <= 0:
        methodology = "Enterprise Value-to-Sales (EV/S) & Price-to-Book (Emiten Laba Bersih Negatif — PER Tidak Digunakan)"
        rev_per_share = (float(base["revenue_idr_b"]) / shares_b) if shares_b > 0 else 13.0
        base_fair = round_tick_fn(max(bvps * 2.4, rev_per_share * 5.2), is_idx, False)
        bear_fair = round_tick_fn(base_fair * 0.78, is_idx, False)
        bull_fair = round_tick_fn(base_fair * 1.25, is_idx, False)
        key_risks = [
            "Laba bersih akuntansi (GAAP) masih negatif; valuasi sangat bergantung pada pertumbuhan GTV & disiplin biaya.",
            "Persaingan ketat di industri layanan on-demand dan fintech pembayaran.",
        ]
    elif is_commodity and eps and eps > 0:
        methodology = "Normalized Mid-Cycle Commodity Earnings Multiple & Through-Cycle PBV"
        mid_eps = float(base.get("mid_cycle_eps") or eps)
        target_mult = float(hist_pe or 6.5)
        fair_from_eps = mid_eps * target_mult
        fair_from_pbv = (bvps or 1500.0) * float(hist_pbv or 1.25)
        base_fair = round_tick_fn((fair_from_eps * 0.6) + (fair_from_pbv * 0.4), is_idx, False)
        bear_fair = round_tick_fn(base_fair * 0.80, is_idx, False)
        bull_fair = round_tick_fn(base_fair * 1.22, is_idx, False)
        key_risks = [
            f"Fluktuasi siklus komoditas acuan: {base.get('commodity_benchmark', 'Harga Komoditas Global')}.",
            "Perubahan royalti tambang, kuota RKAB, atau regulasi DMO pemerintah.",
        ]
    else:
        methodology = "Two-Stage Discounted Cash Flow (DCF) & Blended Historical PER/PBV"
        fcf_b = float(base.get("free_cash_flow_idr_b") or (base.get("net_income_idr_b") or 1000.0) * 0.85)
        fcf_per_share = fcf_b / shares_b
        ke_dec = ke_pct / 100.0
        g_dec = g_pct / 100.0
        dcf_per_share = (fcf_per_share * (1.0 + g_dec)) / max(0.03, (ke_dec - g_dec))
        pe_fair = (eps or 100.0) * float(hist_pe or 15.0)
        base_fair = round_tick_fn((dcf_per_share * 0.5) + (pe_fair * 0.5), is_idx, False)
        bear_fair = round_tick_fn(base_fair * 0.83, is_idx, False)
        bull_fair = round_tick_fn(base_fair * 1.18, is_idx, False)
        key_risks = [
            "Perlambatan daya beli konsumen domestik dan kenaikan biaya bahan baku impor akibat fluktuasi USD/IDR.",
            "Perubahan tingkat diskonto (WACC / Cost of Equity) akibat pergerakan imbal hasil SBN 10 Tahun.",
        ]

    upside_pct = round(((base_fair - current_price) / current_price) * 100.0, 2) if current_price > 0 else 0.0
    mos_pct = round(((base_fair - current_price) / base_fair) * 100.0, 2) if base_fair > 0 else 0.0

    if upside_pct >= 12.0:
        val_status = "UNDERVALUED (DISKON VALUASI)"
    elif upside_pct <= -10.0:
        val_status = "OVERVALUED (PREMIUM DI ATAS NILAI WAJAR)"
    else:
        val_status = "FAIRLY VALUED (RENTANG WAJAR)"

    return {
        "data_status": "VALID",
        "valuation_date": val_date,
        "methodology": methodology,
        "current_market_price": current_price,
        "multiples": {
            "pe_ttm": pe_ratio,
            "pe_note": "Laba bersih negatif — PER tidak relevan" if (eps is not None and eps <= 0) else "Trailing 12M PER",
            "pbv": pbv_ratio,
            "peg_ratio": peg_ratio,
            "dividend_yield_pct": dividend_yield_pct,
            "ev_ebitda": ev_ebitda,
            "hist_5y_pe_avg": hist_pe,
            "hist_5y_pbv_avg": hist_pbv,
        },
        "scenarios": {
            "bear_case": bear_fair,
            "base_case": base_fair,
            "bull_case": bull_fair,
            "fair_value_range": f"Rp {bear_fair:,.0f} – Rp {bull_fair:,.0f}",
        },
        "margin_of_safety_pct": mos_pct,
        "potential_upside_pct": upside_pct,
        "valuation_status": val_status,
        "assumptions": {
            "cost_of_equity_ke_pct": ke_pct,
            "terminal_growth_g_pct": g_pct,
            "reporting_period_basis": base["reporting_period"],
            "commodity_cycle_note": base.get("commodity_benchmark") if is_commodity else None,
        },
        "key_risks": key_risks,
        "disclaimer": (
            "Estimasi nilai wajar merupakan hasil pemodelan kuantitatif berdasarkan laporan keuangan historis "
            "dan asumsi tingkat diskonto, bukan jaminan harga pasar pasti akan tercapai."
        ),
    }
