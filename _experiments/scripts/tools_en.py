"""English translations of TOOLS and SYSTEM_PROMPT for tool-definition language ablation.

This module provides English versions of the 23 AML tool definitions and the system prompt.
Used by benchmark.py with --tools-lang en to evaluate the effect of tool definition language
on function calling accuracy.

Translation scope:
- SYSTEM_PROMPT_EN: Full English translation
- TOOLS_EN: All 23 tool descriptions + parameter descriptions in English
- predict_fraud parameter names: 거래시간대→transaction_time_zone, etc.
"""

from __future__ import annotations

# ── Korean → English parameter name mapping (for predict_fraud) ──
KO_EN_PARAM_MAP: dict[str, str] = {
    "거래일자": "transaction_date",
    "거래시간대": "transaction_time_zone",
    "출금금융회사일련번호": "sender_bank_id",
    "출금계좌일련번호": "sender_account_id",
    "입금금융회사일련번호": "receiver_bank_id",
    "입금계좌일련번호": "receiver_account_id",
    "자금구분": "fund_type",
    "매체구분": "channel_type",
    "거래금액": "transaction_amount",
    "이상거래유형": "fraud_type_code",
}
EN_KO_PARAM_MAP: dict[str, str] = {v: k for k, v in KO_EN_PARAM_MAP.items()}

# ── English System Prompt ──
SYSTEM_PROMPT_EN = """\
You are an Anti-Money Laundering (AML) specialist analyst.
You analyze HOFINET (Electronic Financial Common Network) suspicious transaction detection data to identify and report suspected money laundering activities.

Tool definitions are provided via the API tools field; refer to each tool's name, description, and parameter schema there.

Recommended analysis procedure:
1. get_statistics for overall status overview
2. get_trend_analysis for time-series trend analysis
3. query_transactions for detailed suspicious transaction inquiry
4. detect_ctr_candidates for CTR-eligible high-value or structuring detection
5. score_account_risk for account risk assessment
6. detect_monitoring_alerts for rule-based monitoring alert detection
7. detect_dormant_reactivation for dormant account reactivation detection
8. detect_smurfing_network for fund collection/dispersion pattern detection
9. analyze_channel_risk for channel-specific risk analysis
10. get_receiving_account_profile for receiving account fund inflow analysis
11. analyze_cross_institution_flow for inter-institution fund flow analysis
12. analyze_network for account network analysis (N-hop deep exploration)
13. detect_aml_patterns for circular/layering/mule account pattern detection
14. predict_fraud for fraud probability prediction
15. Only generate_str when sufficient evidence is gathered

STR writing guidelines:
- Always query evidence data with query_transactions before writing STR
- Pass queried transaction records in the transactions parameter when calling generate_str for automatic account/amount/channel extraction
- If predict_fraud results are available, pass the probability value in fraud_probability
- If detect_aml_patterns results are available, include them in aml_patterns

Data schema:
- Table: hofinet (4,732,130 records)
- Columns: transaction_date (YYYYMMDD), transaction_time_zone (0-21, 3-hour intervals), sender_bank_id, sender_account_id, receiver_bank_id, receiver_account_id, fund_type (0,1,3,4), channel_type (1-7), transaction_amount, is_fraud (0/1), fraud_type_code (1-5,7), fraud_description

Fraud types: 1=Sudden Change in Transaction Pattern, 2=Transaction with New Counterparty (most frequent, 63.87%), 3=Split Transaction, 4=Concurrent Multiple Transactions, 5=Same-Day Withdrawal after Large Deposit, 7=Late-Night/Early-Morning Bulk Transactions (note: code 6 unused)
Channel types: 1=PC Banking, 2=Internet Banking, 3=Phone, 4=Mobile Phone, 5=Per-transaction Transfer, 6=Other, 7=Bulk Transfer
Fund types: 0=General, 1=Salary, 3=Other, 4=Inter-bank Auto Transfer

Respond in Korean. Provide specific numbers and evidence in your analysis."""

# ── English Tool Definitions ──
TOOLS_EN: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_transactions",
            "description": "Execute a SQL query on the HOFINET database to retrieve transaction data. Table name is hofinet with columns: transaction_date, transaction_time_zone, sender_bank_id, sender_account_id, receiver_bank_id, receiver_account_id, fund_type, channel_type, transaction_amount, is_fraud, fraud_type_code, fraud_description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT SQL query to execute. Supports aggregation, filtering, grouping on the hofinet table."
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "predict_fraud",
            "description": "Predict the fraud probability of a specific transaction using an XGBoost model. All 6 feature parameters are required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_time_zone": {
                        "type": "integer",
                        "description": "Transaction time zone (0-21, 3-hour intervals). 0=00-03h, 3=03-06h, ..., 21=21-24h"
                    },
                    "sender_bank_id": {
                        "type": "integer",
                        "description": "Sender (withdrawal) financial institution serial number"
                    },
                    "receiver_bank_id": {
                        "type": "integer",
                        "description": "Receiver (deposit) financial institution serial number"
                    },
                    "fund_type": {
                        "type": "integer",
                        "description": "Fund type code. 0=General, 1=Salary, 3=Other, 4=Inter-bank Auto Transfer"
                    },
                    "channel_type": {
                        "type": "integer",
                        "description": "Channel type code. 1=PC Banking, 2=Internet Banking, 3=Phone, 4=Mobile Phone, 5=Per-transaction Transfer, 6=Other, 7=Bulk Transfer"
                    },
                    "transaction_amount": {
                        "type": "integer",
                        "description": "Transaction amount in KRW"
                    }
                },
                "required": ["transaction_time_zone", "sender_bank_id", "receiver_bank_id", "fund_type", "channel_type", "transaction_amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_str",
            "description": "Generate a Suspicious Transaction Report (STR) in official format with sections I-VII based on analysis results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of suspicious activity findings"
                    },
                    "fraud_type": {
                        "type": "string",
                        "description": "Suspected fraud type (e.g., Sudden Change in Transaction Pattern, Split Transaction, Concurrent Multiple Transactions)"
                    },
                    "transactions": {
                        "type": "array",
                        "description": "List of transaction records as evidence. Each record is a dict with transaction fields."
                    },
                    "fraud_probability": {
                        "type": "number",
                        "description": "Fraud probability from predict_fraud (0.0-1.0). Mapped to suspicion level 1-5."
                    },
                    "aml_patterns": {
                        "type": "array",
                        "description": "AML patterns detected by detect_aml_patterns (e.g., circular, layering)"
                    },
                    "tools_used": {
                        "type": "array",
                        "description": "List of tools used during analysis for audit trail"
                    }
                },
                "required": ["summary", "fraud_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_network",
            "description": "Analyze the transaction network around a specific account to identify connected accounts, transaction volumes, and fraud involvement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Account serial number to analyze"
                    },
                    "hops": {
                        "type": "integer",
                        "description": "Network exploration depth (default: 1). Higher values explore further connections."
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "Retrieve overall transaction summary statistics including total count, fraud count, fraud ratio, and fraud type distribution.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_profile",
            "description": "Retrieve comprehensive transaction statistics profile for a specific account including transaction count, total amount, fraud ratio, peak trading hours, and top counterparties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Account serial number to profile"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fraud_type_summary",
            "description": "Retrieve detailed breakdown by fraud type code (1-7) including count, amount statistics, and top financial institutions involved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fraud_type": {
                        "type": "integer",
                        "description": "Fraud type code (1=Sudden Change in Transaction Pattern, 2=Transaction with New Counterparty, 3=Split Transaction, 4=Concurrent Multiple Transactions, 5=Same-Day Withdrawal after Large Deposit, 7=Late-Night/Early-Morning Bulk Transactions). If omitted, returns all types."
                    },
                    "bank_id": {
                        "type": "integer",
                        "description": "Filter by financial institution serial number (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_periods",
            "description": "Compare transaction and fraud statistics between two time periods, calculating change rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period1_start": {
                        "type": "integer",
                        "description": "Start date of first period (YYYYMMDD)"
                    },
                    "period1_end": {
                        "type": "integer",
                        "description": "End date of first period (YYYYMMDD)"
                    },
                    "period2_start": {
                        "type": "integer",
                        "description": "Start date of second period (YYYYMMDD)"
                    },
                    "period2_end": {
                        "type": "integer",
                        "description": "End date of second period (YYYYMMDD)"
                    }
                },
                "required": ["period1_start", "period1_end", "period2_start", "period2_end"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_institution_report",
            "description": "Generate a comprehensive report for a specific financial institution including transaction volume, fraud ratio, top counterparties, and fraud type distribution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_id": {
                        "type": "integer",
                        "description": "Financial institution serial number"
                    }
                },
                "required": ["bank_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rank_risky_transactions",
            "description": "Run batch XGBoost predictions on a random sample and return the top-K highest risk transactions ranked by predicted fraud probability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_size": {
                        "type": "integer",
                        "description": "Number of transactions to sample for prediction (default: 1000)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top risky transactions to return (default: 20)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_aml_patterns",
            "description": "Detect AML-specific patterns using Memgraph graph database. Supports: circular transactions (ring), layering, mule accounts (funnel), shortest path between accounts, and risk scoring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "description": "Pattern type to detect: 'ring' (circular), 'layering', 'funnel' (mule account), 'shortest_path', 'risk_score'"
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "Target account for analysis (required for ring, funnel, risk_score)"
                    },
                    "account_a": {
                        "type": "integer",
                        "description": "Source account for shortest_path"
                    },
                    "account_b": {
                        "type": "integer",
                        "description": "Destination account for shortest_path"
                    },
                    "min_len": {
                        "type": "integer",
                        "description": "Minimum cycle length for ring detection (default: 3)"
                    },
                    "max_len": {
                        "type": "integer",
                        "description": "Maximum cycle length for ring detection (default: 6)"
                    },
                    "min_layers": {
                        "type": "integer",
                        "description": "Minimum layers for layering detection (default: 3)"
                    },
                    "min_inflow": {
                        "type": "integer",
                        "description": "Minimum inflow count for funnel detection (default: 5)"
                    },
                    "max_outflow": {
                        "type": "integer",
                        "description": "Maximum outflow count for funnel detection (default: 2)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)"
                    }
                },
                "required": ["pattern_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_ctr_candidates",
            "description": "Identify CTR (Currency Transaction Report) eligible transactions. mode=high_value finds transactions over threshold (default 10M KRW). mode=structuring detects same-account same-day split transactions that aggregate above threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Detection mode: 'high_value' (single high-value transactions) or 'structuring' (split transaction detection)"
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "Start date filter (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date filter (YYYYMMDD)"
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "Amount threshold in KRW (default: 10000000)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)"
                    }
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_account_risk",
            "description": "Compute a composite risk score (0-100) for a specific account based on 5 behavioral indicators: late-night transaction ratio (weight 0.15), amount anomaly (0.25), counterparty diversity (0.15), velocity change (0.25), and fraud history (0.20).",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Account serial number to evaluate"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_monitoring_alerts",
            "description": "Detect rule-based transaction monitoring alerts. Rules: R001=Late-night bulk, R002=Multi-transaction same day, R003=Round-amount pattern, R004=Institution-concentrated, R005=Pattern sudden change, R006=Dormant reactivation. Use 'all' to run all rules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "Rule ID to apply: 'R001'-'R006' or 'all' for all rules"
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "Start date filter (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date filter (YYYYMMDD)"
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "Filter by specific account (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum alerts to return (default: 100)"
                    }
                },
                "required": ["rule_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_dormant_reactivation",
            "description": "Detect accounts reactivated after extended dormancy period. Identifies potential mule accounts or hidden fund withdrawals based on inactivity duration and reactivation transaction amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dormant_days": {
                        "type": "integer",
                        "description": "Minimum dormancy period in days (default: 180)"
                    },
                    "min_reactivation_amount": {
                        "type": "integer",
                        "description": "Minimum transaction amount for reactivation detection in KRW (default: 1000000)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_smurfing_network",
            "description": "Detect smurfing networks: fund collection (inbound: multiple accounts → single account) or fund dispersion (outbound: single account → multiple accounts) patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Central account to analyze"
                    },
                    "direction": {
                        "type": "string",
                        "description": "Flow direction: 'inbound' (collection) or 'outbound' (dispersion)"
                    },
                    "min_counterparts": {
                        "type": "integer",
                        "description": "Minimum number of counterparties to flag (default: 5)"
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "Start date filter (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date filter (YYYYMMDD)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 20)"
                    }
                },
                "required": ["account_id", "direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend_analysis",
            "description": "Perform time-series trend analysis on transaction data. Returns monthly or quarterly trends for transaction count, fraud ratio, and transaction amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "description": "Time unit: 'monthly' or 'quarterly'"
                    },
                    "date_from": {
                        "type": "integer",
                        "description": "Start date (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date (YYYYMMDD)"
                    }
                },
                "required": ["unit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_channel_risk",
            "description": "Analyze transaction risk by channel (medium type). Includes fraud ratio per channel and channel × time-zone cross-analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "integer",
                        "description": "Start date filter (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date filter (YYYYMMDD)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_receiving_account_profile",
            "description": "Profile a receiving (deposit) account from the inflow perspective. Analyzes fund inflow patterns, source institutions, and sender account characteristics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Receiving account serial number to profile"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_cross_institution_flow",
            "description": "Analyze fund flows between institution pairs (sender institution → receiver institution). Identifies high-volume corridors and suspicious inter-institutional patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "integer",
                        "description": "Start date filter (YYYYMMDD)"
                    },
                    "date_to": {
                        "type": "integer",
                        "description": "End date filter (YYYYMMDD)"
                    },
                    "min_transactions": {
                        "type": "integer",
                        "description": "Minimum transaction count to include a pair (default: 100)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum institution pairs to return (default: 20)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_fiu_reference_types",
            "description": "Search FIU (Financial Intelligence Unit) suspicious transaction reference types by keyword or industry. Covers structuring, late-night transactions, non-face-to-face, virtual assets, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search keyword (e.g., 'structuring', 'late-night', 'virtual asset')"
                    },
                    "industry": {
                        "type": "string",
                        "description": "Industry filter (e.g., 'bank', 'securities', 'insurance')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_str_fields",
            "description": "Validate required fields of an STR (Suspicious Transaction Report) draft against official format requirements including header, reporting institution, transactor info, and transaction details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "str_draft": {
                        "type": "object",
                        "description": "STR draft object to validate"
                    }
                },
                "required": ["str_draft"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_aml_glossary",
            "description": "Look up AML (Anti-Money Laundering) terminology definitions. Covers: CDD (Customer Due Diligence), EDD (Enhanced Due Diligence), STR (Suspicious Transaction Report), CTR (Currency Transaction Report), RBA (Risk-Based Approach), PEP (Politically Exposed Person), MLRO (Money Laundering Reporting Officer), FATF, FIU, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "AML term to look up (e.g., 'CDD', 'STR', 'PEP')"
                    }
                },
                "required": ["term"]
            }
        }
    },
]
