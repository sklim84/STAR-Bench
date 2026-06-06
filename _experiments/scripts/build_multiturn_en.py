"""Build the English multi-turn STR benchmark (benchmarks_multiturn_en/).

Mirrors the single-turn EN convention (benchmarks_en/): only the natural-language
fields are translated to English; the tool interface (tool_calls, tool_result,
context_ref — including Korean parameter/result keys) is kept byte-identical so the
multi-turn evaluator and context_ref logic are unaffected ("EN query + KR tool
interface" setting, the multi-turn analog of the EN-KR condition).

Translated fields: scenario, fraud_type_name (scenario-level); content, note (turn-level).
Untouched: id, sub_category, fraud_type, turn, tool_calls, tool_calls_alt,
tool_result, context_ref, expect_clarification.

Deterministic: unique strings are collected per field in sorted order to derive
stable ids (F/S/C/N), which key the embedded English map TR. Re-running reproduces
the same output.

Usage:  PYTHONPATH=. python _experiments/scripts/build_multiturn_en.py
"""
import json
import re
from pathlib import Path

SB = Path(__file__).resolve().parents[2]
SRC = SB / "benchmarks_multiturn" / "cases_str_workflow.json"
OUT_DIR = SB / "benchmarks_multiturn_en"
OUT = OUT_DIR / "cases_str_workflow.json"

# ── English translations keyed by deterministic id (see _collect) ──────────────
TR = {
    # fraud_type_name
    "F000": "Sudden change in transaction pattern",
    "F001": "Same-day withdrawal after large deposit",
    "F002": "Other",
    "F003": "Simultaneous multiple-transaction requests",
    "F004": "Structured transactions",
    "F005": "New-recipient transaction",
    "F006": "Late-night/early-morning high-volume transactions",
    # scenario
    "S000": "Check AML term -> pattern type missing -> clarification -> detection -> STR",
    "S001": "CTR mode unspecified -> clarification -> structuring detection -> risk -> STR",
    "S002": "R001 late-night high-volume -> profile (context_ref) -> risk (context_ref) -> institution report -> STR",
    "S003": "R002 same-day multiple-transaction alert -> account query (context_ref) -> CTR structuring (context_ref) -> STR",
    "S004": "R003 fixed-amount transactions -> profile (context_ref) -> CTR structuring (context_ref) -> AML term -> STR",
    "S005": "R004 institution-concentration alert -> cross-institution flow (context_ref) -> transaction query -> STR",
    "S006": "Sudden change in transaction pattern, account specified directly -> query, prediction, network analysis -> draft STR",
    "S007": "Transaction query -> deposit-account profile (context_ref) -> fund-collection analysis (context_ref) -> STR",
    "S008": "Transaction time slot missing -> clarification -> prediction -> profile -> draft STR",
    "S009": "Transaction query -> prediction -> STR draft validation (context_ref) -> draft STR",
    "S010": "Transaction query -> prediction (context_ref) -> network (context_ref) -> AML pattern shortest path -> STR",
    "S011": "Transaction query -> prediction (context_ref) -> network (context_ref) -> risk (context_ref) -> FIU reference -> STR",
    "S012": "Transaction query -> prediction (context_ref) -> deposit profile (context_ref) -> smurfing -> STR",
    "S013": "Same-day withdrawal after large deposit suspected -> per-type status query -> transaction query -> prediction -> draft STR",
    "S014": "Search keyword missing -> clarification -> FIU reference type -> transaction query -> STR validation -> STR",
    "S015": "Account number missing -> clarification -> account query -> prediction -> draft STR",
    "S016": "Account number mistyped -> clarification -> profile after correction -> deposit profile -> STR",
    "S017": "Institution-level suspicious-transaction query -> identify top withdrawal account -> profile and risk -> draft STR",
    "S018": "Institution number missing -> clarification -> cross-institution flow analysis -> transaction query -> STR",
    "S019": "Period missing -> clarification -> institution report after specifying period -> risk -> STR",
    "S020": "Cross-institution fund flow analysis -> query transactions in the concentrated segment -> AML pattern detection -> draft STR",
    "S021": "Institution report -> cross-institution flow (context_ref) -> layering (context_ref) -> STR",
    "S022": "Institution report -> profile of account with most anomalies (context_ref) -> prediction -> STR",
    "S023": "Monitoring rule unspecified -> clarification -> R001 late-night high-volume -> account query -> STR",
    "S024": "Monitoring alert -> R005 abrupt-change account query (context_ref) -> period comparison (context_ref) -> STR",
    "S025": "Monitoring alert detection -> fixed-amount transaction account query -> risk assessment -> draft STR",
    "S026": "Analysis direction missing -> clarification -> specify smurfing direction -> query -> STR",
    "S027": "Query transactions of account suspected of structuring -> smurfing analysis -> network -> draft STR",
    "S028": "Comparison period missing -> clarification -> period comparison -> transaction query -> STR",
    "S029": "Late-night/early-morning high-volume FIU reference -> transaction query -> receiving profile (context_ref) -> risk -> STR",
    "S030": "Late-night/early-morning high-volume transactions suspected -> FIU reference type query -> transaction query -> risk assessment -> draft STR",
    "S031": "Risk ranking -> top account network (context_ref) -> circular-transaction detection -> STR",
    "S032": "Type status -> top-institution transaction query (context_ref) -> risk (context_ref) -> STR",
    "S033": "Insufficient suspicion - few transactions -> low risk -> normal network -> STR not required",
    "S034": "Insufficient suspicion - transaction query -> low prediction -> no pattern detected -> STR not required",
    "S035": "Insufficient suspicion - institution report -> transaction query -> low risk -> STR not required",
    "S036": "Insufficient suspicion - low prediction -> no monitoring alert -> judge STR not required",
    "S037": "Insufficient suspicion - normal profile -> low prediction -> no pattern -> STR not required",
    "S038": "Suspicion type unspecified -> clarification -> specify simultaneous multiple-transaction requests -> query and prediction -> STR",
    "S039": "Deposit-account profile -> fund-collection pattern -> circular-transaction detection -> draft STR",
    "S040": "Overall statistics query -> risky-transaction ranking -> prediction -> draft STR",
    "S041": "STR requested with insufficient information -> clarification -> information provided -> investigation -> draft STR",
    "S042": "Channel risk analysis -> identify late-night ATM transaction account -> prediction -> draft STR",
    "S043": "Channel analysis -> late-night internet-banking transaction query (context_ref) -> profile -> network (context_ref) -> STR",
    "S044": "Statistics -> same-day withdrawal after large deposit type -> transaction query (context_ref) -> FIU reference -> STR",
    "S045": "Statistics -> structured-transaction type -> top-account funnel detection (context_ref) -> STR",
    "S046": "Trend -> surge-month transaction query (context_ref) -> channel analysis -> prediction (context_ref) -> STR",
    "S047": "Trend analysis -> surge-period comparison -> transaction query -> draft STR",
    "S048": "Dormant account reactivation detection -> profile query -> CTR check -> draft STR",
    "S049": "Dormancy detection -> profile (context_ref) -> CTR (context_ref) -> structured transactions -> STR",
    # content
    "C000": "Analyze the channel-level risk for December.",
    "C001": "Predict the top-ranked transaction again.",
    "C002": "Analyze the network of the top-ranked account.",
    "C003": "Compare Q3 and Q4 of 2024.",
    "C004": "Look at the Q4 2024 transactions.",
    "C005": "Analyze the channel-level risk for Q4 2024.",
    "C006": "Compare the first and second halves of 2024.",
    "C007": "Find the shortest path from 29501 to 99801.",
    "C008": "Analyze the network of 29501.",
    "C009": "Find accounts reactivated after being dormant for more than 300 days.",
    "C010": "Check the transactions of account 33045.",
    "C011": "Assess the risk of account 44201.",
    "C012": "Predict the fraud probability of the 44892 transaction.",
    "C013": "Draft an STR under the Other type for the Q4 surge.",
    "C014": "Query the suspicious transactions that surged in Q4.",
    "C015": "Assess the risk of account 66801.",
    "C016": "Query in detail the suspicious transactions on the 73->305 segment.",
    "C017": "Check the profile of account 77501.",
    "C018": "Look at account 88923.",
    "C019": "Look at the profile of account 99801.",
    "C020": "Find suspicious accounts among late-night ATM transactions.",
    "C021": "Check on the CTR.",
    "C022": "Check whether it is subject to CTR.",
    "C023": "Also check whether it is subject to CTR.",
    "C024": "Also check the FIU reference type and draft the STR.",
    "C025": "I want to check the FIU reference type.",
    "C026": "Check the R001 late-night high-volume transaction alerts.",
    "C027": "Look at the account transactions of the largest case among the R001 late-night high-volume transactions.",
    "C028": "Check the R002 same-day multiple-transaction alerts.",
    "C029": "Query in detail the transactions of R003 fixed-amount transaction account 22801.",
    "C030": "Check the R003 fixed-amount transaction alerts.",
    "C031": "Check the R004 institution-concentration transaction alerts.",
    "C032": "Is this at a level that requires drafting an STR?",
    "C033": "Would drafting an STR be necessary?",
    "C034": "Draft the STR.",
    "C035": "Validate the STR draft.",
    "C036": "I need to draft an STR; can you help?",
    "C037": "Is there a need to draft an STR?",
    "C038": "Look at the profile of the account with the most transactions.",
    "C039": "Query the transactions of the account that changed most abruptly.",
    "C040": "Query in detail the transactions of the account with the most transactions.",
    "C041": "Look at the transactions of the most-involved account.",
    "C042": "Look at the profile of the deposit account that receives the most.",
    "C043": "Look at the profile of the account that was dormant the longest.",
    "C044": "Query the profile of the account with the most suspicious transactions.",
    "C045": "Check the profile of that account with the most suspicious transactions.",
    "C046": "Query the transactions of the month with the most suspicious transactions.",
    "C047": "Analyze the flow of the most concentrated institution pair.",
    "C048": "Look at the profile of the account with the largest amount.",
    "C049": "Also check the FIU reference type related to a sudden change in transaction pattern and draft the STR.",
    "C050": "Draft the STR for a sudden change in transaction pattern in a structured form.",
    "C051": "There is a transaction suspected of a sudden change in transaction pattern; please analyze it.",
    "C052": "Draft the STR for a sudden change in transaction pattern.",
    "C053": "Run all transaction monitoring alerts.",
    "C054": "Predict the transaction with amount 85 million won, withdrawal institution 134, deposit institution 88, fund type 4, media type 5.",
    "C055": "The transaction time slot is 15:00.",
    "C056": "Check the abrupt transaction-pattern change (R005) alerts.",
    "C057": "Also check the FIU reference type related to same-day withdrawal after large deposit.",
    "C058": "Tell me the status of suspicious transactions related to same-day withdrawal after large deposit.",
    "C059": "Search for items related to same-day withdrawal after large deposit.",
    "C060": "Look at the detailed status of same-day withdrawal after large deposit.",
    "C061": "Draft the STR for same-day withdrawal after large deposit.",
    "C062": "Please draft the STR for same-day withdrawal after large deposit.",
    "C063": "Account 11045 looks somewhat suspicious; please analyze it.",
    "C064": "Check whether account 22901 is a case of simultaneous multiple-transaction requests. Query its transactions.",
    "C065": "There are suspicious transactions between accounts 29501 and 99801. Look at 29501's transactions.",
    "C066": "Query the transaction history of account 33201.",
    "C067": "Query the transactions of account 33801.",
    "C068": "Query the transactions of account 41205 suspected of simultaneous multiple-transaction requests.",
    "C069": "Suspicious transactions were found in account 42105. An STR needs to be drafted.",
    "C070": "Analyze the smurfing pattern of account 55089.",
    "C071": "Account 55901 is suspected of late-night/early-morning high-volume transactions. Look at its profile.",
    "C072": "Query the transactions of account 77234.",
    "C073": "Query the transactions of account 81402.",
    "C074": "Account 88234 has many deposits. Look at this account's transactions.",
    "C075": "Query the transaction history of account 91205. Structuring is suspected.",
    "C076": "Account 99301 is suspected of a sudden change in transaction pattern. Query its transactions.",
    "C077": "Analyze the account.",
    "C078": "Explain what structuring is.",
    "C079": "Check whether that account corresponds to a funnel pattern.",
    "C080": "Query that account's transactions.",
    "C081": "Check that account's layering pattern.",
    "C082": "Query that withdrawal account's transactions.",
    "C083": "Then run AML pattern detection.",
    "C084": "Create a suspicious-transaction report for financial institution 205.",
    "C085": "Look at the status of financial institution 305.",
    "C086": "Query the status of financial institution 73.",
    "C087": "Query financial institution 88's transactions related to same-day withdrawal after large deposit.",
    "C088": "Report the status of financial institution 88.",
    "C089": "Analyze the cross-institution fund flow.",
    "C090": "Also run a network analysis.",
    "C091": "Run a network analysis.",
    "C092": "Try analyzing the network too.",
    "C093": "Also analyze the network.",
    "C094": "It looks like simultaneous multiple-transaction requests. The victim seems to have sent money over the phone. Query the transaction history.",
    "C095": "Tell me the status of the simultaneous multiple-transaction request type.",
    "C096": "Should I draft an STR for simultaneous multiple-transaction requests?",
    "C097": "Draft the STR for simultaneous multiple-transaction requests.",
    "C098": "Predict the representative transaction.",
    "C099": "Try predicting the representative transaction.",
    "C100": "Predict the fraud probability of the representative transaction.",
    "C101": "Look at the profile of the deposit account that received the most money.",
    "C102": "The fund flow between the two financial institutions is abnormal. Analyze it.",
    "C103": "Detect the layering pattern.",
    "C104": "Check whether there is a layering pattern.",
    "C105": "Explain what layering is.",
    "C106": "Also check the monitoring alerts.",
    "C107": "Check the monitoring alerts.",
    "C108": "Analyze the quarterly trend.",
    "C109": "Synthesize the analysis results and draft the STR on suspicion of a sudden change in transaction pattern.",
    "C110": "Look in detail at the structured-transaction type.",
    "C111": "Also check the structured-transaction (funnel) pattern.",
    "C112": "Draft the STR for structured transactions.",
    "C113": "Check the CTR to see if structuring is suspected.",
    "C114": "Detect cases suspected of structuring.",
    "C115": "Try checking the circular-transaction pattern too.",
    "C116": "Also check the circular-transaction pattern.",
    "C117": "The new-recipient transaction type is the most common. Look at the related transactions in detail.",
    "C118": "Draft the STR on suspicion of a new-recipient transaction.",
    "C119": "New-recipient transactions are the most common. Draft the STR.",
    "C120": "Draft the STR for a new-recipient transaction.",
    "C121": "It is a new-recipient transaction with many transactions, so query the transactions.",
    "C122": "Query the transactions of the account with the most late-night internet-banking activity.",
    "C123": "Query the FIU reference type related to late-night/early-morning high-volume transactions.",
    "C124": "Check the FIU reference type related to late-night/early-morning high-volume transactions.",
    "C125": "Draft the STR for late-night/early-morning high-volume transactions.",
    "C126": "After prediction, draft the STR for simultaneous multiple-transaction requests.",
    "C127": "Predict it.",
    "C128": "Analyze the monthly suspicious-transaction trend.",
    "C129": "Show the top 5 risky transactions.",
    "C130": "Rank the highest-risk transactions.",
    "C131": "Also run a risk assessment.",
    "C132": "Run a risk assessment.",
    "C133": "Assess the risk.",
    "C134": "Based on this transaction data, predict the fraud probability.",
    "C135": "Predict this transaction.",
    "C136": "Predict the fraud probability of these transactions.",
    "C137": "Predict the fraud probability of a representative case among this account's transactions.",
    "C138": "Assess this account's risk.",
    "C139": "Check this account's profile.",
    "C140": "Also look at the report for the financial institution this account belongs to.",
    "C141": "Analyze the inbound direction, i.e., the money coming into this account.",
    "C142": "Also look at the deposit pattern coming into this account.",
    "C143": "Compare November and December for this account.",
    "C144": "Also analyze this account's transaction network.",
    "C145": "Check whether this account is suspected of structuring.",
    "C146": "Check this account's structuring.",
    "C147": "Also check this account's risk.",
    "C148": "Assess this account's risk.",
    "C149": "Look at this account's deposit (receiving) profile.",
    "C150": "Analyze this account's fund-dispersion pattern.",
    "C151": "Analyze this account's fund-collection pattern.",
    "C152": "Query the suspicious transactions on this segment.",
    "C153": "Analyze the flow between this institution and the counterpart institution with the most suspicious transactions.",
    "C154": "Also analyze this deposit account's fund-collection pattern.",
    "C155": "Show the status by suspicious-transaction type.",
    "C156": "Predict the fraud probability.",
    "C157": "Please predict the fraud probability.",
    "C158": "Suspicious transactions seem to have surged. Compare the periods.",
    "C159": "Now draft the STR.",
    "C160": "Analyze the fund-inflow pattern of deposit account 445012.",
    "C161": "Check whether there is a fund-collection pattern.",
    "C162": "Query the overall transaction statistics.",
    "C163": "First show the overall statistics.",
    "C164": "Synthesize everything analyzed so far and draft the STR right away on suspicion of structured transactions.",
    "C165": "Analyze the recent channel-level risk.",
    "C166": "The withdrawal account is 44290.",
    "C167": "The withdrawal account is 55201, and it is a December 2024 transaction. Simultaneous multiple-transaction requests are suspected.",
    "C168": "The withdrawal account is 67301. Look at the Q4 2024 transactions.",
    "C169": "Suspicious activity is suspected in withdrawal account 78432. Query this account's recent transaction history.",
    "C170": "Query the transactions of withdrawal account 82301.",
    "C171": "Can you identify the withdrawal account? Find recent transactions in this amount range at institution 134.",
    "C172": "I heard there are many suspicious transactions at withdrawal institution 134. Query the related transactions.",
    "C173": "The withdrawal is institution 73 and the deposit is institution 305.",
    "C174": "Predict a representative case among the telebanking transactions.",
    "C175": "Query the suspicious transactions that surged in the second half.",
    "C176": "Detect reactivated dormant accounts.",
    # note
    "N000": "Check the abrupt change from November to December",
    "N001": "Dormant for more than 300 days",
    "N002": "Q4 suspicious-transaction detail",
    "N003": "73->305 suspicious-transaction detail",
    "N004": "Score 81, high risk",
    "N005": "Inflow from 89 accounts - unspecified-many receiving pattern",
    "N006": "Score 91, high risk",
    "N007": "AML term explanation",
    "N008": "ATM + late-night filter",
    "N009": "FIU reference type for sudden change in transaction pattern",
    "N010": "FIU reference type for gambling",
    "N011": "FIU late-night/early-morning high-volume transactions",
    "N012": "Check FIU reference type for late-night/early-morning high-volume transactions",
    "N013": "Query FIU reference type",
    "N014": "Q3 vs Q4 comparison",
    "N015": "R001 alert",
    "N016": "R002 alert",
    "N017": "R003 alert",
    "N018": "R004 institution concentration",
    "N019": "R005 alert",
    "N020": "Validate STR draft",
    "N021": "XGBoost batch prediction ranking",
    "N022": "context_ref: 45201 circular-transaction detection",
    "N023": "context_ref: 55801 risk",
    "N024": "context_ref: inbound analysis with 661023",
    "N025": "context_ref: 72301 profile",
    "N026": "context_ref: 73->305 flow",
    "N027": "context_ref: score 89, high risk",
    "N028": "context_ref: R001 largest-amount account profile",
    "N029": "context_ref: R005 most-abruptly-changed account -> SQL query",
    "N030": "context_ref: risk_score->fraud_probability",
    "N031": "context_ref: smurfing_score -> fraud_probability",
    "N032": "context_ref: account with most structured transactions -> funnel check",
    "N033": "context_ref: account with most late-night internet banking",
    "N034": "context_ref: predicted probability->fraud_probability",
    "N035": "context_ref: deposit-account inbound analysis",
    "N036": "context_ref: highest-risk account -> network analysis",
    "N037": "context_ref: most-concentrated institution-pair flow",
    "N038": "context_ref: account with most withdrawals -> transaction query",
    "N039": "context_ref: transactions of account with most cases",
    "N040": "context_ref: profile of account with most cases",
    "N041": "context_ref: transactions of the top account",
    "N042": "context_ref: transactions of account with most anomalies - few suspicious transactions",
    "N043": "context_ref: transactions of withdrawal account with most anomalies",
    "N044": "context_ref: layering of withdrawal account with most anomalies",
    "N045": "context_ref: receiving profile of top deposit account",
    "N046": "context_ref: month with most suspicious transactions -> query",
    "N047": "context_ref: longest-dormant account -> profile",
    "N048": "context_ref: Turn 1 top deposit account -> account_id",
    "N049": "context_ref: Turn 1's account with most suspicious transactions -> account_id",
    "N050": "context_ref: Turn 3 predicted probability -> fraud_probability",
    "N051": "direction (inbound/outbound) unspecified -> must ask back",
    "N052": "funnel structured-transaction STR",
    "N053": "funnel pattern detection",
    "N054": "check inbound collection pattern",
    "N055": "inbound fund collection",
    "N056": "mode (high_value/structuring) unspecified",
    "N057": "check outbound dispersion pattern",
    "N058": "pattern_type (ring/layering/funnel, etc.) unspecified",
    "N059": "Link risk_score 78 -> fraud_probability 0.78. Structured-transaction STR item VI: third-party name, one-off account",
    "N060": "rule_id unspecified, but executable as 'all' so run directly",
    "N061": "detect in structuring mode",
    "N062": "structuring detection",
    "N063": "Sudden change in transaction pattern STR",
    "N064": "Transaction suspected of a sudden change in transaction pattern",
    "N065": "Transaction query",
    "N066": "Counterparty diversity 0.95 - characteristic of late-night/early-morning high-volume transactions",
    "N067": "transaction time slot missing -> required predict_fraud parameter",
    "N068": "FIU type for same-day withdrawal after large deposit",
    "N069": "Same-day withdrawal after large deposit STR",
    "N070": "Query account suspected of same-day withdrawal after large deposit",
    "N071": "Status of same-day withdrawal after large deposit",
    "N072": "search keyword missing",
    "N073": "Check whether account number 78432 is retained in the conversation context",
    "N074": "Account number specified -> query directly (base)",
    "N075": "No account number",
    "N076": "No account number, period, etc. -> must ask back",
    "N077": "No core information at all (account number, period, suspicion type, etc.). No tool can be called, so asking back is the correct answer.",
    "N078": "Account number is specified, so it can be queried directly (base type)",
    "N079": "Check high-value cash transaction",
    "N080": "Confirm high-risk grade",
    "N081": "Structuring STR",
    "N082": "Identify account by amount",
    "N083": "Institution-level query. Both query_transactions and get_institution_report are correct.",
    "N084": "Query institution 88 + suspicious-transaction type 5",
    "N085": "Abrupt-change new-recipient transaction STR",
    "N086": "Surge-period new-recipient transaction STR",
    "N087": "Surge phenomenon, Other STR",
    "N088": "Query after specifying the period",
    "N089": "Institution 305 status - low suspicious-transaction ratio",
    "N090": "Institution 73 status",
    "N091": "Institution status",
    "N092": "Cross-institution flow STR",
    "N093": "Full cross-institution flow analysis",
    "N094": "Check cross-institution flow",
    "N095": "Cross-institution -> layering STR",
    "N096": "Institution report",
    "N097": "The institution report can be queried without a period, so run directly",
    "N098": "Institution-concentration new-recipient transaction STR",
    "N099": "Network",
    "N100": "Network analysis",
    "N101": "Check network connections",
    "N102": "Simultaneous multiple-transaction requests STR",
    "N103": "The recommended actions in the simultaneous multiple-transaction requests STR include 'immediate freeze', 'victim protection', and 'referral to investigative authorities'",
    "N104": "Query simultaneous multiple-transaction request transactions",
    "N105": "When simultaneous multiple-transaction requests are suspected, checking the CTR is a natural follow-up investigation",
    "N106": "Status of simultaneous multiple-transaction requests",
    "N107": "Simultaneous multiple-transaction requests + fund-collection STR",
    "N108": "Representative transaction prediction",
    "N109": "After asking back, the user provides info -> now queryable",
    "N110": "Info provided after asking back",
    "N111": "Layering STR",
    "N112": "Layering, sudden change in transaction pattern STR",
    "N113": "Query layering source account",
    "N114": "Layering pattern detection",
    "N115": "Very low probability",
    "N116": "Composite pattern STR",
    "N117": "Check quarterly trend",
    "N118": "Structured-transaction STR",
    "N119": "Complete the structured-transaction STR",
    "N120": "Structured-transaction status",
    "N121": "Structuring STR",
    "N122": "Structuring account risk",
    "N123": "Check structuring",
    "N124": "Two comparison periods missing",
    "N125": "First half vs second half comparison",
    "N126": "Few transactions, high anomaly ratio",
    "N127": "Circular-transaction STR",
    "N128": "Circular-transaction detection",
    "N129": "Circular-transaction + fund-collection STR",
    "N130": "Smurfing score very low",
    "N131": "Predict after supplementing the time slot",
    "N132": "New-recipient transaction STR",
    "N133": "Late-night ATM transaction prediction",
    "N134": "Late-night ATM structuring STR",
    "N135": "Late-night time-slot transaction prediction",
    "N136": "Late-night/early-morning high-volume transactions STR",
    "N137": "Account suspected of late-night/early-morning high-volume transactions",
    "N138": "Query account suspected of late-night/early-morning high-volume transactions",
    "N139": "Query late-night high-volume transaction account",
    "N140": "Late-night internet-banking structured-transaction STR",
    "N141": "No alert",
    "N142": "Ambiguous which account to view -> the 'largest case' is 88923, but the user may need to specify it directly",
    "N143": "Which financial institution is not specified",
    "N144": "Which period/account to view is not specified -> must ask back",
    "N145": "Which suspicion is unspecified",
    "N146": "Prediction",
    "N147": "Perform prediction",
    "N148": "Predicted probability low -> normal",
    "N149": "Term explanation",
    "N150": "Monthly trend",
    "N151": "Risk ranking",
    "N152": "Query after confirming the type",
    "N153": "Query with type code 5",
    "N154": "Insufficient suspicion -> judge STR not required. Without calling a tool, the correct answer is 'insufficient grounds to file an STR at this stage; continue monitoring'",
    "N155": "Insufficient suspicion: prediction 8%, risk score 18 (low), 1 suspicious transaction. STR not required; recommending periodic monitoring is correct",
    "N156": "Insufficient suspicion: 0 suspicious transactions, prediction 5%, smurfing 0.12. STR not required; recommend periodic monitoring",
    "N157": "Insufficient suspicion: 0 suspicious transactions, risk score 15 (low), 3 connections normal. STR not required",
    "N158": "Insufficient suspicion: 4 suspicious transactions, risk score 22 (low). STR not required; recommending continued monitoring is correct",
    "N159": "Suspicion type unspecified -> must ask back which type of suspicion",
    "N160": "0 suspicious transactions",
    "N161": "Only 1 suspicious transaction",
    "N162": "Few suspicious transactions",
    "N163": "Generate the STR by synthesizing prior-turn results (probability 0.91, network info) into the summary",
    "N164": "Deposit-side profile",
    "N165": "Low risk",
    "N166": "Run all rules",
    "N167": "Overall statistics",
    "N168": "Overall status",
    "N169": "Grasp overall status",
    "N170": "Phone-channel large-transfer prediction",
    "N171": "Normal network",
    "N172": "Fixed-amount transaction account detail",
    "N173": "Fixed-amount transaction structuring STR",
    "N174": "Comprehensive sudden change in transaction pattern STR - max length of 6 turns",
    "N175": "Medium-risk grade",
    "N176": "Channel-level analysis",
    "N177": "Channel-level risk status",
    "N178": "Re-confirm highest-risk transaction",
    "N179": "Shortest-path STR",
    "N180": "Shortest-path detection",
    "N181": "Withdrawal account transactions",
    "N182": "Query withdrawal account transactions",
    "N183": "Withdrawal account profile",
    "N184": "Predict using a representative case from Turn 1 transaction data",
    "N185": "Predict using a representative case from Turn 2 transaction data",
    "N186": "Telebanking late-night prediction",
    "N187": "Run after confirming the pattern type",
    "N188": "Second-half suspicious transactions",
    "N189": "Key evaluation: whether 'that account' correctly references Turn 1's 78432",
    "N190": "Key evaluation: whether 'this account' is retained as 78432",
    "N191": "Reactivated-after-dormancy account profile",
    "N192": "Dormant -> reactivated structured-transaction STR",
    "N193": "Dormant account reactivation scan",
}

_HANGUL = re.compile(r"[가-힣]")


def _collect(data):
    """Reproduce id->ko exactly as the extraction step (sorted unique per field)."""
    buckets = {"F": set(), "S": set(), "C": set(), "N": set()}
    for sc in data:
        if sc.get("fraud_type_name"):
            buckets["F"].add(sc["fraud_type_name"])
        if sc.get("scenario"):
            buckets["S"].add(sc["scenario"])
        for t in sc["turns"]:
            if t.get("content"):
                buckets["C"].add(t["content"])
            if t.get("note"):
                buckets["N"].add(t["note"])
    ko_by_id, id_by_ko = {}, {}
    for tag in ["F", "S", "C", "N"]:
        for i, s in enumerate(sorted(buckets[tag])):
            sid = f"{tag}{i:03d}"
            ko_by_id[sid] = s
            id_by_ko[s] = sid
    return ko_by_id, id_by_ko


def _en(s, id_by_ko, missing):
    sid = id_by_ko.get(s)
    if sid is None or sid not in TR:
        missing.append((sid, s))
        return s
    return TR[sid]


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    ko_by_id, id_by_ko = _collect(data)

    # sanity: every collected id must have a translation
    untranslated = [sid for sid in ko_by_id if sid not in TR]
    if untranslated:
        raise SystemExit(f"ERROR: {len(untranslated)} ids lack translations: {untranslated[:10]}")

    missing = []
    out = []
    for sc in data:
        nsc = json.loads(json.dumps(sc, ensure_ascii=False))  # deep copy
        if nsc.get("scenario"):
            nsc["scenario"] = _en(nsc["scenario"], id_by_ko, missing)
        if nsc.get("fraud_type_name"):
            nsc["fraud_type_name"] = _en(nsc["fraud_type_name"], id_by_ko, missing)
        for t in nsc["turns"]:
            if t.get("content"):
                t["content"] = _en(t["content"], id_by_ko, missing)
            if t.get("note"):
                t["note"] = _en(t["note"], id_by_ko, missing)
        out.append(nsc)

    # ── validation ────────────────────────────────────────────────────────────
    assert len(out) == len(data), "scenario count changed"
    for o, k in zip(out, data):
        assert len(o["turns"]) == len(k["turns"]), f"turn count changed in {k['id']}"
        for to, tk in zip(o["turns"], k["turns"]):
            # tool interface must be byte-identical
            for fld in ("tool_calls", "tool_calls_alt", "tool_result", "context_ref",
                        "expect_clarification", "turn"):
                assert to.get(fld) == tk.get(fld), f"{fld} changed in {k['id']} turn {tk['turn']}"
    # no Korean left in translated fields
    kor_left = []
    for o in out:
        for fld in ("scenario", "fraud_type_name"):
            if o.get(fld) and _HANGUL.search(o[fld]):
                kor_left.append((o["id"], fld, o[fld]))
        for t in o["turns"]:
            for fld in ("content", "note"):
                if t.get(fld) and _HANGUL.search(t[fld]):
                    kor_left.append((o["id"], f"turn{t['turn']}.{fld}", t[fld]))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"Wrote {OUT}  ({len(out)} scenarios, {sum(len(s['turns']) for s in out)} turns)")
    if missing:
        print(f"  WARN: {len(missing)} strings had no mapping (kept KR): {missing[:5]}")
    if kor_left:
        print(f"  WARN: {len(kor_left)} translated fields still contain Korean: {kor_left[:5]}")
    else:
        print("  OK: no Korean remains in translated fields; tool interface unchanged.")


if __name__ == "__main__":
    main()
