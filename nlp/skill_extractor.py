"""
SkillScope NLP Module: Rule-Based ESCO Skill Extractor & Independent Benchmark Evaluator
Courses: Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)

Features:
1. Cleans raw HTML job descriptions safely (inline tags stripped without splitting words,
   block tags replaced with whitespace, HTML entities decoded).
2. Integrates the 3,015-occupation European Commission ESCO Parquet taxonomy in `data/bronze/`
   to link 86 canonical skills across 15 categories to ESCO competency concepts and occupation counts.
3. Implements fast compiled token & n-gram phrase matching + alias normalization
   ("JS" -> "JavaScript", "PowerBI" -> "Power BI") + explicit context disambiguation rules
   for ambiguous tokens ("R", "Go", "Rust", "React", "Spark", "Swift", "Excel", "transformers",
   "SAS", "PLC", "Ruby", "Salesforce").
4. Provides `analyze_job_description()` with matched phrases and character spans for live UI highlighting.
5. Evaluates extraction quality against the independent 100-posting ground-truth benchmark
   (`nlp/ground_truth_100.json`) covering 75 tech/data roles and 25 non-tech hard negatives.
"""

import html
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|br|li|ul|ol|tr|td|th|h[1-6]|section|article|header|footer|blockquote)\b[^>]*>",
    re.IGNORECASE,
)
INLINE_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def clean_html_text(raw: Optional[str]) -> str:
    """
    Cleans HTML job descriptions safely without breaking mid-word inline tags
    (e.g., `<b>T</b>rust` becomes `Trust`, NOT `T rust`).
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ""
    s = str(raw)
    s = BLOCK_TAG_RE.sub(" ", s)
    s = INLINE_TAG_RE.sub("", s)
    s = html.unescape(s)
    return WHITESPACE_RE.sub(" ", s).strip()


# ============================================================================
# 1. STANDARDIZED ESCO-ALIGNED SKILL TAXONOMY & ALIAS DICTIONARY (86 SKILLS)
# ============================================================================
# Preserves keys 1..68 in exact order; appends 69..86 high-impact skills.
# (skill_name, esco_concept_ref, skill_type, category_name, parent_category, is_emerging, aliases_list, esco_competency_keywords)
CORE_ESCO_SKILLS = [
    # Programming Languages (1..15)
    ("Python", "urn:skillscope:esco-aligned:python", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["python", "python3", "python 3"], ["computer programming", "develop software", "scripts", "data analysis"]),
    ("SQL", "urn:skillscope:esco-aligned:sql", "skill/competence", "Programming Languages", "Data & Analytics", 0, ["sql", "t-sql", "pl/sql", "ansi sql", "structured query language"], ["database", "query", "sql", "data models"]),
    ("JavaScript", "urn:skillscope:esco-aligned:javascript", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["javascript", "java script", "js", "ecmascript", "es6"], ["web programming", "user interface", "software", "web application"]),
    ("TypeScript", "urn:skillscope:esco-aligned:typescript", "skill/competence", "Programming Languages", "Software & Engineering", 1, ["typescript"], ["web programming", "software design", "web application"]),
    ("Java", "urn:skillscope:esco-aligned:java", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["java", "java 8", "java 11", "java 17", "java ee", "j2ee", "jvm"], ["computer programming", "software", "object-oriented"]),
    ("C++", "urn:skillscope:esco-aligned:cpp", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["c++", "cpp", "c/c++"], ["computer programming", "embedded", "software"]),
    ("C#", "urn:skillscope:esco-aligned:csharp", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["c#", "c sharp", "csharp", ".net c#"], ["computer programming", "software"]),
    ("R", "urn:skillscope:esco-aligned:r-language", "skill/competence", "Programming Languages", "Data & Analytics", 0, ["r programming", "r-project", "rstudio", "r studio", "cran"], ["statistics", "statistical", "data analysis"]),
    ("Go", "urn:skillscope:esco-aligned:golang", "skill/competence", "Programming Languages", "Software & Engineering", 1, ["golang", "go language", "go programming"], ["computer programming", "network", "system"]),
    ("Rust", "urn:skillscope:esco-aligned:rust", "skill/competence", "Programming Languages", "Software & Engineering", 1, ["rustlang"], ["computer programming", "system", "software"]),
    ("Scala", "urn:skillscope:esco-aligned:scala", "skill/competence", "Programming Languages", "Data & Analytics", 0, ["scala"], ["computer programming", "data", "software"]),
    ("PHP", "urn:skillscope:esco-aligned:php", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["php", "php7", "php8"], ["web programming", "web", "database"]),
    ("Swift", "urn:skillscope:esco-aligned:swift", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["swiftui"], ["mobile", "application", "software"]),
    ("Kotlin", "urn:skillscope:esco-aligned:kotlin", "skill/competence", "Programming Languages", "Software & Engineering", 1, ["kotlin"], ["mobile", "application", "software"]),
    ("Bash / Shell", "urn:skillscope:esco-aligned:bash-shell", "skill/competence", "Programming Languages", "Cloud & DevOps", 0, ["bash", "shell scripting", "zsh", "powershell", "unix shell"], ["operating system", "scripts", "ict system"]),

    # Data Science, AI & Machine Learning (16..26)
    ("Machine Learning", "urn:skillscope:esco-aligned:machine-learning", "knowledge", "AI & Machine Learning", "Data & Analytics", 1, ["machine learning", "predictive modeling", "supervised learning", "unsupervised learning"], ["artificial intelligence", "data mining", "algorithms", "statistics"]),
    ("Deep Learning", "urn:skillscope:esco-aligned:deep-learning", "knowledge", "AI & Machine Learning", "Data & Analytics", 1, ["deep learning", "neural networks", "neural network", "convolutional neural", "recurrent neural"], ["artificial intelligence", "algorithms", "model"]),
    ("Natural Language Processing", "urn:skillscope:esco-aligned:nlp", "knowledge", "AI & Machine Learning", "Data & Analytics", 1, ["natural language processing", "nlp", "text mining", "spacy", "nltk", "named entity recognition", "language modeling"], ["artificial intelligence", "language", "text"]),
    ("Generative AI & LLMs", "urn:skillscope:esco-aligned:generative-ai-llms", "skill/competence", "AI & Machine Learning", "Data & Analytics", 1, ["llm", "llms", "large language models", "large language model", "generative ai", "genai", "langchain", "openai", "prompt engineering", "hugging face", "vector database", "pinecone"], ["artificial intelligence", "language", "model"]),
    ("Computer Vision", "urn:skillscope:esco-aligned:computer-vision", "knowledge", "AI & Machine Learning", "Data & Analytics", 1, ["computer vision", "opencv", "image processing", "object detection", "yolo"], ["image", "artificial intelligence", "visual"]),
    ("PyTorch", "urn:skillscope:esco-aligned:pytorch", "skill/competence", "AI & Machine Learning", "Data & Analytics", 1, ["pytorch"], ["artificial intelligence", "software", "algorithms"]),
    ("TensorFlow", "urn:skillscope:esco-aligned:tensorflow", "skill/competence", "AI & Machine Learning", "Data & Analytics", 0, ["tensorflow", "keras"], ["artificial intelligence", "software", "algorithms"]),
    ("Scikit-Learn", "urn:skillscope:esco-aligned:scikit-learn", "skill/competence", "AI & Machine Learning", "Data & Analytics", 0, ["scikit-learn", "sklearn", "scikit learn"], ["statistics", "data mining", "algorithms"]),
    ("Pandas & NumPy", "urn:skillscope:esco-aligned:pandas-numpy", "skill/competence", "Data Analysis & Statistics", "Data & Analytics", 0, ["pandas", "numpy", "scipy", "matplotlib", "seaborn", "polars"], ["data analysis", "statistics", "analyse data"]),
    ("Statistics & A/B Testing", "urn:skillscope:esco-aligned:statistics-ab-testing", "knowledge", "Data Analysis & Statistics", "Data & Analytics", 0, ["statistics", "statistical analysis", "statistical modeling", "hypothesis testing", "a/b testing", "econometrics", "linear regression", "logistic regression", "regression analysis", "time series"], ["statistics", "statistical", "analyse data"]),
    ("MLOps", "urn:skillscope:esco-aligned:mlops", "skill/competence", "AI & Machine Learning", "Data & Analytics", 1, ["mlops", "mlflow", "kubeflow", "model deployment", "sagemaker", "vertex ai"], ["artificial intelligence", "ict system", "deploy"]),

    # Data Engineering, Warehousing & BI (27..39)
    ("Power BI", "urn:skillscope:esco-aligned:power-bi", "skill/competence", "Business Intelligence", "Data & Analytics", 1, ["power bi", "powerbi", "ms power bi", "power query", "dax"], ["business intelligence", "data", "visual", "report"]),
    ("Tableau", "urn:skillscope:esco-aligned:tableau", "skill/competence", "Business Intelligence", "Data & Analytics", 0, ["tableau", "tableau desktop", "tableau server"], ["business intelligence", "visual", "report"]),
    ("Looker", "urn:skillscope:esco-aligned:looker", "skill/competence", "Business Intelligence", "Data & Analytics", 0, ["looker", "lookml", "looker studio"], ["business intelligence", "report", "data"]),
    ("Excel", "urn:skillscope:esco-aligned:excel", "skill/competence", "Business Intelligence", "Business & Operations", 0, ["microsoft excel", "ms excel", "advanced excel", "pivot tables", "pivot table", "vlookup", "excel vba", "spreadsheets"], ["spreadsheet", "office", "data"]),
    ("ETL & Data Pipelines", "urn:skillscope:esco-aligned:etl-pipelines", "skill/competence", "Data Engineering", "Data & Analytics", 0, ["etl", "elt", "data pipeline", "data pipelines", "data integration", "data ingestion"], ["data", "database", "integrate"]),
    ("Data Warehousing", "urn:skillscope:esco-aligned:data-warehousing", "knowledge", "Data Engineering", "Data & Analytics", 0, ["data warehouse", "data warehousing", "star schema", "snowflake schema", "dimensional modeling", "olap", "data mart", "kimball", "duckdb"], ["data models", "ict data architecture", "database"]),
    ("Apache Spark", "urn:skillscope:esco-aligned:apache-spark", "skill/competence", "Data Engineering", "Data & Analytics", 0, ["apache spark", "pyspark", "spark sql"], ["data", "distributed", "database"]),
    ("Apache Kafka", "urn:skillscope:esco-aligned:apache-kafka", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["kafka", "apache kafka", "event streaming", "kinesis", "rabbitmq"], ["data", "network", "system"]),
    ("Apache Airflow", "urn:skillscope:esco-aligned:apache-airflow", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["airflow", "apache airflow", "dagster", "prefect"], ["data", "automate", "workflow"]),
    ("dbt", "urn:skillscope:esco-aligned:dbt", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["dbt", "data build tool"], ["data models", "database", "data"]),
    ("Snowflake", "urn:skillscope:esco-aligned:snowflake", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["snowflake", "snowflake db", "snowflake cloud"], ["database", "cloud", "data"]),
    ("Databricks", "urn:skillscope:esco-aligned:databricks", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["databricks", "data bricks", "delta lake", "lakehouse"], ["data", "cloud", "database"]),
    ("BigQuery", "urn:skillscope:esco-aligned:bigquery", "skill/competence", "Data Engineering", "Data & Analytics", 1, ["bigquery", "big query", "google bigquery", "redshift", "amazon redshift", "azure synapse", "clickhouse"], ["database", "cloud", "data"]),

    # Databases (40..45)
    ("PostgreSQL", "urn:skillscope:esco-aligned:postgresql", "skill/competence", "Databases", "Data & Analytics", 0, ["postgresql", "postgres", "postgis"], ["database", "manage database", "sql"]),
    ("MySQL", "urn:skillscope:esco-aligned:mysql", "skill/competence", "Databases", "Data & Analytics", 0, ["mysql", "mariadb"], ["database", "manage database", "sql"]),
    ("Microsoft SQL Server", "urn:skillscope:esco-aligned:mssql", "skill/competence", "Databases", "Data & Analytics", 0, ["sql server", "ms sql", "mssql", "ssrs", "ssis", "ssas"], ["database", "manage database", "sql"]),
    ("Oracle Database", "urn:skillscope:esco-aligned:oracle-db", "skill/competence", "Databases", "Data & Analytics", 0, ["oracle db", "oracle database", "oracle sql", "oracle 12c", "oracle 19c", "oracle rds", "plsql"], ["database", "manage database", "sql"]),
    ("MongoDB", "urn:skillscope:esco-aligned:mongodb", "skill/competence", "Databases", "Software & Engineering", 0, ["mongodb", "nosql", "dynamodb", "cassandra"], ["database", "data", "storage"]),
    ("Redis", "urn:skillscope:esco-aligned:redis", "skill/competence", "Databases", "Software & Engineering", 0, ["redis", "memcached", "elasticsearch"], ["database", "cache", "search"]),

    # Web, Backend & Frontend Frameworks (46..54)
    ("React", "urn:skillscope:esco-aligned:react", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["reactjs", "react.js", "next.js", "nextjs"], ["web application", "user interface", "web programming"]),
    ("Angular", "urn:skillscope:esco-aligned:angular", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["angular", "angularjs"], ["web application", "user interface", "web programming"]),
    ("Vue.js", "urn:skillscope:esco-aligned:vuejs", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["vue.js", "vuejs", "nuxt", "nuxt.js", "svelte"], ["web application", "user interface", "web programming"]),
    ("Node.js", "urn:skillscope:esco-aligned:nodejs", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["node.js", "nodejs", "express.js", "nestjs"], ["web application", "web programming", "server"]),
    ("FastAPI & Flask", "urn:skillscope:esco-aligned:fastapi-flask", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 1, ["fastapi", "flask", "django"], ["web application", "web programming", "software"]),
    ("Spring Boot", "urn:skillscope:esco-aligned:spring-boot", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["spring boot", "spring framework", "hibernate"], ["web application", "software", "architecture"]),
    (".NET Core", "urn:skillscope:esco-aligned:dotnet-core", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, [".net", ".net core", "asp.net", "entity framework"], ["web application", "software", "architecture"]),
    ("REST & GraphQL APIs", "urn:skillscope:esco-aligned:rest-graphql", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["rest api", "rest apis", "restful", "graphql", "grpc", "microservices", "api design"], ["software architecture", "integrate", "web"]),
    ("HTML & CSS", "urn:skillscope:esco-aligned:html-css", "skill/competence", "Web & Application Frameworks", "Software & Engineering", 0, ["html", "html5", "css", "css3", "tailwind", "tailwind css", "sass"], ["web", "user interface", "design"]),

    # Cloud, DevOps & Security (55..63)
    ("AWS", "urn:skillscope:esco-aligned:aws", "skill/competence", "Cloud Platforms", "Cloud & DevOps", 0, ["aws", "amazon web services", "ec2", "aws glue", "aws lambda", "eks"], ["cloud", "ict infrastructure", "server"]),
    ("Microsoft Azure", "urn:skillscope:esco-aligned:azure", "skill/competence", "Cloud Platforms", "Cloud & DevOps", 1, ["azure", "microsoft azure", "azure data factory", "azure devops", "azure synapse"], ["cloud", "ict infrastructure", "server"]),
    ("Google Cloud Platform (GCP)", "urn:skillscope:esco-aligned:gcp", "skill/competence", "Cloud Platforms", "Cloud & DevOps", 1, ["gcp", "google cloud", "google cloud platform"], ["cloud", "ict infrastructure", "server"]),
    ("Docker", "urn:skillscope:esco-aligned:docker", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 0, ["docker", "containerization"], ["ict infrastructure", "deploy", "software"]),
    ("Kubernetes", "urn:skillscope:esco-aligned:kubernetes", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 1, ["kubernetes", "k8s", "helm", "openshift"], ["ict infrastructure", "deploy", "network"]),
    ("Terraform & IaC", "urn:skillscope:esco-aligned:terraform-iac", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 1, ["terraform", "ansible", "cloudformation", "infrastructure as code", "iac"], ["ict infrastructure", "automate", "configuration"]),
    ("CI/CD & Git", "urn:skillscope:esco-aligned:cicd-git", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 0, ["git", "github", "gitlab", "ci/cd", "continuous integration", "continuous delivery", "jenkins", "github actions", "bitbucket", "version control", "circleci", "argocd"], ["software", "test", "configuration"]),
    ("Linux", "urn:skillscope:esco-aligned:linux", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 0, ["linux", "ubuntu", "red hat", "rhel", "unix"], ["operating system", "ict system", "server"]),
    ("Cybersecurity & IAM", "urn:skillscope:esco-aligned:cybersecurity-iam", "knowledge", "Cybersecurity", "Cloud & DevOps", 1, ["cybersecurity", "cyber security", "information security", "infosec", "siem", "penetration testing", "identity and access management", "zero trust", "owasp", "iso 27001", "security operations center"], ["ict security", "information security", "identity management"]),

    # Product, Business & Soft Skills (64..68)
    ("Agile & Scrum", "urn:skillscope:esco-aligned:agile-scrum", "knowledge", "Project & Product Management", "Business & Operations", 0, ["agile", "scrum", "kanban", "jira", "confluence", "sprint planning"], ["project management", "team", "manage"]),
    ("Product Management", "urn:skillscope:esco-aligned:product-management", "skill/competence", "Project & Product Management", "Business & Operations", 0, ["product management", "product roadmap", "product strategy", "user stories"], ["product", "strategy", "manage"]),
    ("Data Governance & Quality", "urn:skillscope:esco-aligned:data-governance", "knowledge", "Data Analysis & Statistics", "Data & Analytics", 1, ["data governance", "data quality", "master data", "mdm", "gdpr", "data privacy", "data cataloging"], ["data quality", "data confidentiality", "policy"]),
    ("Stakeholder Communication", "urn:skillscope:esco-aligned:stakeholder-comm", "skill/competence", "Leadership & Communication", "Business & Operations", 0, ["stakeholder management", "executive presentation", "data storytelling"], ["communicate", "stakeholders", "present"]),
    ("Financial & Business Analysis", "urn:skillscope:esco-aligned:business-analysis", "skill/competence", "Project & Product Management", "Business & Operations", 0, ["financial modeling", "business analysis", "requirements gathering", "fp&a", "variance analysis"], ["analyse business", "financial", "requirements"]),

    # High-Impact Domain, QA, Design, Observability & Enterprise Skills (69..86)
    ("Test Automation (Selenium / Cypress)", "urn:skillscope:esco-aligned:test-automation", "skill/competence", "QA & Testing", "Software & Engineering", 0, ["selenium", "cypress", "playwright", "appium", "pytest", "junit", "test automation", "automated testing", "jmeter", "postman"], ["software testing", "execute software tests", "test suite"]),
    ("UI/UX Design & Figma", "urn:skillscope:esco-aligned:ui-ux-figma", "skill/competence", "Design & UX", "Product & Design", 1, ["figma", "adobe xd", "wireframing", "user research", "usability testing", "ui/ux", "ux design", "design systems"], ["user interface", "prototype", "design"]),
    ("Networking & Infrastructure", "urn:skillscope:esco-aligned:networking-infra", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 0, ["tcp/ip", "cisco", "firewall", "firewalls", "vpn", "bgp", "dns", "dhcp", "vlan", "active directory", "vmware", "load balancing", "sd-wan", "network administration"], ["network", "ict infrastructure", "hardware"]),
    ("Observability & Monitoring", "urn:skillscope:esco-aligned:observability-monitoring", "skill/competence", "DevOps & Infrastructure", "Cloud & DevOps", 1, ["grafana", "prometheus", "datadog", "splunk", "new relic", "kibana", "cloudwatch", "dynatrace", "opentelemetry", "elk stack"], ["monitor", "ict system", "troubleshoot"]),
    ("ServiceNow & ITIL / ITSM", "urn:skillscope:esco-aligned:servicenow-itil", "skill/competence", "Enterprise Systems & IT", "Business & Operations", 0, ["servicenow", "itil", "itsm", "incident management", "change management", "zendesk", "service desk"], ["ict troubleshooting", "support", "incident"]),
    ("Statistical Tools (SAS / SPSS / MATLAB / Qlik)", "urn:skillscope:esco-aligned:statistical-tools", "skill/competence", "Data Analysis & Statistics", "Data & Analytics", 0, ["spss", "matlab", "stata", "alteryx", "qlik", "qlik sense", "qlikview"], ["statistics", "statistical", "analyse data"]),
    ("Embedded Systems & Firmware", "urn:skillscope:esco-aligned:embedded-firmware", "skill/competence", "Hardware & Embedded", "Engineering & Hardware", 0, ["firmware", "rtos", "microcontroller", "microcontrollers", "embedded c", "arm cortex", "fpga", "verilog", "vhdl", "can bus"], ["embedded", "hardware", "microcontroller"]),
    ("CAD & Industrial Automation", "urn:skillscope:esco-aligned:cad-automation", "skill/competence", "Hardware & Embedded", "Engineering & Hardware", 0, ["autocad", "solidworks", "revit", "catia", "ansys", "scada", "cad/cam"], ["cad", "engineering", "design"]),
    ("Ruby & Rails", "urn:skillscope:esco-aligned:ruby-rails", "skill/competence", "Programming Languages", "Software & Engineering", 0, ["ruby on rails", "rspec"], ["web programming", "computer programming", "software"]),
    ("ERP Systems (SAP / NetSuite / Workday)", "urn:skillscope:esco-aligned:erp-systems", "skill/competence", "Enterprise Systems & IT", "Business & Operations", 0, ["sap erp", "s/4hana", "sap s/4hana", "sap mm", "sap fico", "sap hana", "netsuite", "workday erp", "workday financials", "oracle erp", "dynamics 365", "peoplesoft", "erp system"], ["enterprise resource", "business processes", "manage"]),
    ("CRM Platforms (Salesforce / HubSpot)", "urn:skillscope:esco-aligned:crm-platforms", "skill/competence", "Enterprise Systems & IT", "Business & Operations", 0, ["salesforce crm", "salesforce admin", "salesforce developer", "hubspot", "dynamics crm", "crm platform", "crm system"], ["customer relationship", "sales", "client"]),
    ("Six Sigma & Lean Operations", "urn:skillscope:esco-aligned:six-sigma-lean", "knowledge", "Operations & Supply Chain", "Business & Operations", 0, ["six sigma", "lean six sigma", "lean manufacturing", "kaizen", "fmea", "value stream mapping"], ["quality assurance", "process", "efficiency"]),
    ("Regulatory Compliance (HIPAA / SOC 2 / SOX)", "urn:skillscope:esco-aligned:regulatory-compliance", "knowledge", "Governance & Compliance", "Business & Operations", 1, ["hipaa", "soc 2", "soc2", "sox compliance", "sarbanes-oxley", "pci-dss", "pci dss", "nist", "fedramp", "iso 9001", "osha"], ["compliance", "regulations", "legal requirements"]),
    ("Project Management & SDLC (PMP)", "urn:skillscope:esco-aligned:pmp-sdlc", "skill/competence", "Project & Product Management", "Business & Operations", 0, ["pmp", "sdlc", "smartsheet", "ms project", "microsoft project", "gantt", "budget management", "project lifecycle"], ["project management", "plan", "budget"]),
    ("Financial Accounting & Audit (GAAP)", "urn:skillscope:esco-aligned:financial-accounting", "knowledge", "Finance & Accounting", "Business & Operations", 0, ["gaap", "quickbooks", "accounts payable", "accounts receivable", "general ledger", "financial reporting", "account reconciliation", "cpa"], ["accounting", "financial statements", "audit"]),
    ("Digital Marketing & SEO (GA4)", "urn:skillscope:esco-aligned:digital-marketing", "skill/competence", "Marketing & Growth", "Business & Operations", 0, ["seo", "google analytics", "ga4", "google ads", "marketo", "email marketing", "paid search", "marketing automation", "campaign management"], ["marketing", "digital", "campaign"]),
    ("Supply Chain & Procurement", "urn:skillscope:esco-aligned:supply-chain", "knowledge", "Operations & Supply Chain", "Business & Operations", 0, ["supply chain", "procurement", "inventory management", "logistics management", "warehouse management", "wms", "demand planning", "vendor management"], ["supply chain", "logistics", "inventory"]),
    ("Talent Acquisition & HRIS", "urn:skillscope:esco-aligned:talent-hris", "skill/competence", "Human Resources", "Business & Operations", 0, ["talent acquisition", "hris", "workday hcm", "full-cycle recruiting", "applicant tracking system", "technical recruiting"], ["recruitment", "human resources", "staff"]),
]


class ESCOSkillExtractor:
    """
    Rule-based NLP skill extractor with alias normalization, HTML cleanup,
    context disambiguation for ambiguous tokens, ESCO occupation linkage,
    and span-aware live job description analysis.
    """

    def __init__(self, esco_parquet_path: Optional[str] = None):
        self.skills_catalog: List[Dict] = []
        self.categories: Dict[str, Dict] = {}
        self.name_to_key: Dict[str, int] = {}
        self.key_to_name: Dict[int, str] = {}

        # Context regexes for ambiguous short/polysemous tokens
        self.r_context_re = re.compile(
            r"(?:\b(?:python|sql|sas|spss|matlab|stata)\s*(?:,|/|and|or)\s*R\b|"
            r"\bR\s*(?:,|/|and|or)\s*(?:python|sql|sas|spss|matlab|stata)\b|"
            r"\b(?:in|using|with|experience\s+(?:in|with)|proficiency\s+in|knowledge\s+of)\s+R\b|"
            r"\bR\s+(?:programming|language|studio|shiny|markdown|packages)\b)",
        )
        self.go_context_re = re.compile(
            r"(?:\b(?:python|java|rust|c\+\+|ruby|perl|node\.?js|typescript)\s*(?:,|/|and|or)\s*Go\b|"
            r"\bGo\s*(?:,|/|and|or)\s*(?:python|java|rust|c\+\+|ruby|perl|node\.?js|typescript)\b|"
            r"\b(?:Golang|Go\s+developer|Go\s+engineer|Go\s+backend|programming\s+in\s+Go|Go\s+programming)\b)",
            re.IGNORECASE,
        )
        self.rust_context_re = re.compile(r"\bRust\b")
        self.react_context_re = re.compile(r"\bReact\b")
        self.spark_context_re = re.compile(r"\bSpark\b", re.IGNORECASE)
        self.swift_context_re = re.compile(r"\bSwift\b")
        self.excel_bare_re = re.compile(r"\bExcel\b")
        self.excel_verb_re = re.compile(
            r"\b(?:to\s+excel|will\s+excel|can\s+excel|must\s+excel|you\s+excel|excel\s+in|excel\s+at)\b",
            re.IGNORECASE,
        )
        self.transformers_ai_re = re.compile(
            r"\b(?:hugging\s*face\s+transformers|transformers\s+library|vision\s+transformers|bert|pytorch|tensorflow|deep\s+learning|nlp)\b",
            re.IGNORECASE,
        )
        self.iam_context_re = re.compile(r"\bIAM\b")
        self.soc_analyst_re = re.compile(
            r"\b(?:soc\s+analyst|soc\s+engineer|security\s+operations\s+center|\bSOC\b\s*\(\s*security\s+operations)\b",
            re.IGNORECASE,
        )
        self.oracle_context_re = re.compile(r"\bOracle\b")
        self.vue_context_re = re.compile(r"\bVue\b")
        self.sas_context_re = re.compile(r"\bSAS\b")
        self.plc_context_re = re.compile(r"\bPLC\b")
        self.ruby_context_re = re.compile(r"\bRuby\b", re.IGNORECASE)
        self.salesforce_context_re = re.compile(r"\bSalesforce\b", re.IGNORECASE)
        self.sap_context_re = re.compile(r"\bSAP\b")

        self._build_catalog(esco_parquet_path)

    def _build_catalog(self, esco_parquet_path: Optional[str] = None):
        cat_idx = 1
        self.unigram_aliases: Dict[str, Tuple[int, str]] = {}
        self.ngram_aliases: Dict[Tuple[str, ...], Tuple[int, str]] = {}
        self.token_re = re.compile(
            r"(?:ci/cd|c/c\+\+|pl/sql|s/4hana|ui/ux|tcp/ip|cad/cam|node\.js|react\.js|vue\.js|next\.js|nuxt\.js|express\.js|asp\.net|\.net|"
            r"[a-z0-9+#]+(?:[.-][a-z0-9+#]+)*)"
        )

        self.esco_raw_df = None
        esco_skill_texts: List[str] = []
        if esco_parquet_path and os.path.exists(esco_parquet_path):
            try:
                self.esco_raw_df = pd.read_parquet(esco_parquet_path)
                esco_skill_texts = [str(x).lower() for x in self.esco_raw_df["skills"].fillna("")]
            except Exception:
                self.esco_raw_df = None

        for idx, (name, uri, stype, cat, parent_cat, is_em, aliases, esco_kws) in enumerate(CORE_ESCO_SKILLS, start=1):
            if cat not in self.categories:
                self.categories[cat] = {
                    "category_key": cat_idx,
                    "category_name": cat,
                    "parent_category": parent_cat,
                }
                cat_idx += 1

            skill_key = idx
            self.name_to_key[name] = skill_key
            self.key_to_name[skill_key] = name

            occ_count = 0
            if esco_skill_texts and esco_kws:
                occ_count = sum(1 for txt in esco_skill_texts if any(kw in txt for kw in esco_kws))

            self.skills_catalog.append({
                "skill_key": skill_key,
                "skill_name": name,
                "taxonomy_id": uri,
                "skill_type": stype,
                "category_key": self.categories[cat]["category_key"],
                "category_name": cat,
                "parent_category": parent_cat,
                "is_emerging": is_em,
                "aliases": aliases,
                "esco_occupation_count": occ_count,
            })

            for a in aliases:
                toks = self.token_re.findall(a.lower())
                if not toks:
                    continue
                if len(toks) == 1:
                    self.unigram_aliases[toks[0]] = (skill_key, name)
                else:
                    self.ngram_aliases[tuple(toks)] = (skill_key, name)

    def get_dimension_tables(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Returns dim_skill_category and dim_skill DataFrames."""
        df_cat = pd.DataFrame(list(self.categories.values()))
        df_skill = pd.DataFrame([
            {
                "skill_key": s["skill_key"],
                "skill_name": s["skill_name"],
                "taxonomy_id": s["taxonomy_id"],
                "skill_type": s["skill_type"],
                "category_key": s["category_key"],
                "is_emerging": s["is_emerging"],
                "esco_occupation_count": s["esco_occupation_count"],
                "version_num": 1,
                "is_current": 1,
            }
            for s in self.skills_catalog
        ])
        return df_cat, df_skill

    def _add_hit(self, counts: Dict[int, int], names: Dict[int, str], skill_name: str, inc: int = 1):
        sk_key = self.name_to_key[skill_name]
        counts[sk_key] = counts.get(sk_key, 0) + inc
        names[sk_key] = skill_name

    def extract_from_text(self, text: str, listed_skills: str = "") -> List[Dict]:
        """
        Extracts standardized ESCO-aligned skills from raw job description + listed skills string
        using O(N) hash-table token/n-gram matching + context disambiguation rules.
        """
        combined = f"{listed_skills or ''} \n {text or ''}"
        if not combined.strip():
            return []

        lower_comb = combined.lower()
        toks = self.token_re.findall(lower_comb)
        if not toks:
            return []

        counts: Dict[int, int] = {}
        names: Dict[int, str] = {}
        n_toks = len(toks)
        uni_map = self.unigram_aliases
        ng_map = self.ngram_aliases

        for i, t in enumerate(toks):
            info = uni_map.get(t)
            if info:
                sk_key, sk_name = info
                counts[sk_key] = counts.get(sk_key, 0) + 1
                names[sk_key] = sk_name

            if i + 1 < n_toks:
                bg = (t, toks[i + 1])
                info2 = ng_map.get(bg)
                if info2:
                    sk_key, sk_name = info2
                    counts[sk_key] = counts.get(sk_key, 0) + 1
                    names[sk_key] = sk_name

                if i + 2 < n_toks:
                    tg = (t, toks[i + 1], toks[i + 2])
                    info3 = ng_map.get(tg)
                    if info3:
                        sk_key, sk_name = info3
                        counts[sk_key] = counts.get(sk_key, 0) + 1
                        names[sk_key] = sk_name

        tok_set = set(toks)
        found_names = set(names.values())

        # Context disambiguation rules for short/polysemous tokens
        if "R" not in found_names and self.r_context_re.search(combined):
            self._add_hit(counts, names, "R")

        if "Go" not in found_names and self.go_context_re.search(combined):
            self._add_hit(counts, names, "Go")

        if "Rust" not in found_names and self.rust_context_re.search(combined):
            if found_names & {"Python", "C++", "Go", "Java", "Linux", "Docker", "Kubernetes", "AWS"} or (
                tok_set & {"cargo", "compiler", "systems", "programming", "developer", "engineer"}
            ):
                self._add_hit(counts, names, "Rust")

        if "React" not in found_names and self.react_context_re.search(combined):
            if found_names & {"JavaScript", "TypeScript", "HTML & CSS", "Node.js", "Angular", "Vue.js", "REST & GraphQL APIs", "Java"} or (
                tok_set & {"frontend", "front-end", "redux", "ui", "developer", "engineer", "web", "fullstack", "full-stack"}
            ):
                self._add_hit(counts, names, "React")

        if "Vue.js" not in found_names and self.vue_context_re.search(combined):
            if found_names & {"JavaScript", "TypeScript", "HTML & CSS", "React", "Angular", "Node.js"}:
                self._add_hit(counts, names, "Vue.js")

        if "Apache Spark" not in found_names and self.spark_context_re.search(combined):
            if (found_names & {"Python", "SQL", "Scala", "Apache Kafka", "Apache Airflow", "Databricks", "Snowflake", "BigQuery", "ETL & Data Pipelines", "Data Warehousing", "AWS"}) and not (
                "play and spark" in lower_comb
            ):
                self._add_hit(counts, names, "Apache Spark")

        if "Swift" not in found_names and self.swift_context_re.search(combined):
            if found_names & {"Kotlin"} or (tok_set & {"ios", "xcode", "objective-c", "mobile", "apple", "macos", "uikit"}):
                self._add_hit(counts, names, "Swift")

        if "Excel" not in found_names and self.excel_bare_re.search(combined):
            if not self.excel_verb_re.search(combined):
                if (found_names & {"SQL", "Power BI", "Tableau", "Statistics & A/B Testing", "Financial & Business Analysis"}) or (
                    tok_set & {"word", "powerpoint", "outlook", "office", "spreadsheet", "spreadsheets", "pivot", "vlookup", "vba", "analyst", "reporting", "macros"}
                ):
                    self._add_hit(counts, names, "Excel")

        if "Deep Learning" not in found_names and "transformers" in tok_set:
            if self.transformers_ai_re.search(combined):
                self._add_hit(counts, names, "Deep Learning")

        if "Cybersecurity & IAM" not in found_names:
            if self.soc_analyst_re.search(combined) or (
                self.iam_context_re.search(combined)
                and (found_names & {"AWS", "Microsoft Azure", "Google Cloud Platform (GCP)", "Linux", "Python"} or tok_set & {"security", "okta", "sso", "identity", "access", "active"})
            ):
                self._add_hit(counts, names, "Cybersecurity & IAM")

        if "Oracle Database" not in found_names and self.oracle_context_re.search(combined):
            if found_names & {"SQL", "PostgreSQL", "MySQL", "Microsoft SQL Server", "ETL & Data Pipelines", "Data Warehousing"} or (
                tok_set & {"database", "databases", "rds", "dba", "pl/sql", "plsql"}
            ):
                self._add_hit(counts, names, "Oracle Database")

        if "Statistical Tools (SAS / SPSS / MATLAB / Qlik)" not in found_names and self.sas_context_re.search(combined):
            if found_names & {"R", "Python", "SQL", "Statistics & A/B Testing", "Excel"} or (
                tok_set & {"statistical", "analytics", "data", "spss", "stata", "tableau"}
            ):
                self._add_hit(counts, names, "Statistical Tools (SAS / SPSS / MATLAB / Qlik)")

        if "CAD & Industrial Automation" not in found_names and self.plc_context_re.search(combined):
            if tok_set & {"scada", "hmi", "automation", "allen", "bradley", "siemens", "controls", "ladder", "electrical"}:
                self._add_hit(counts, names, "CAD & Industrial Automation")

        if "Ruby & Rails" not in found_names and self.ruby_context_re.search(combined):
            if found_names & {"Python", "JavaScript", "Java", "Go", "PostgreSQL", "HTML & CSS", "CI/CD & Git"} or (
                tok_set & {"rails", "programming", "scripting", "backend", "engineer", "developer"}
            ):
                self._add_hit(counts, names, "Ruby & Rails")

        if "ERP Systems (SAP / NetSuite / Workday)" not in found_names and self.sap_context_re.search(combined):
            if tok_set & {"erp", "procurement", "hana", "abap", "fico", "mm", "sd", "supply", "finance", "transaction", "analyst", "power"}:
                self._add_hit(counts, names, "ERP Systems (SAP / NetSuite / Workday)")

        if "CRM Platforms (Salesforce / HubSpot)" not in found_names and self.salesforce_context_re.search(combined):
            if not re.search(r"\b(?:companies\s+like|such\s+as)\b[^.]{0,60}\bSalesforce\b", combined, re.I):
                if tok_set & {"crm", "apex", "lightning", "admin", "administrator", "sales", "marketing", "operations", "analyst", "developer"}:
                    self._add_hit(counts, names, "CRM Platforms (Salesforce / HubSpot)")

        results = []
        for sk_key, count in counts.items():
            conf = min(0.99, 0.84 + 0.05 * min(count, 3))
            results.append({
                "skill_key": sk_key,
                "skill_name": names[sk_key],
                "mention_count": count,
                "confidence": round(conf, 3),
            })

        return results

    def analyze_job_description(self, raw_text: str, title: str = "") -> Dict:
        """
        Live JD Analyzer for the Interactive NLP Lab: cleans HTML, extracts skills,
        attaches ESCO metadata, and finds highlight spans inside `cleaned_text`.
        """
        cleaned_body = clean_html_text(raw_text)
        cleaned_full = f"{title.strip()}. {cleaned_body}".strip() if title.strip() else cleaned_body
        extracted = self.extract_from_text(cleaned_full)
        extracted.sort(key=lambda x: (-x["confidence"], -x["mention_count"], x["skill_name"]))

        catalog_by_key = {s["skill_key"]: s for s in self.skills_catalog}
        spans = []
        enriched = []
        for item in extracted:
            meta = catalog_by_key[item["skill_key"]]
            aliases = list(dict.fromkeys([meta["skill_name"].lower()] + meta["aliases"]))
            # Find non-overlapping matches for highlighting in cleaned_full
            matched_terms = set()
            for al in sorted(aliases, key=len, reverse=True):
                pat = re.compile(rf"(?<!\w){re.escape(al)}(?!\w)", re.IGNORECASE)
                for m in pat.finditer(cleaned_full):
                    matched_terms.add(m.group(0))
                    spans.append({
                        "start": m.start(),
                        "end": m.end(),
                        "text": m.group(0),
                        "skill_key": item["skill_key"],
                        "skill_name": item["skill_name"],
                        "category_name": meta["category_name"],
                    })
                    if len(spans) > 120:
                        break
            enriched.append({
                **item,
                "category_name": meta["category_name"],
                "parent_category": meta["parent_category"],
                "taxonomy_id": meta["taxonomy_id"],
                "esco_occupation_count": meta["esco_occupation_count"],
                "is_emerging": meta["is_emerging"],
                "matched_terms": sorted(matched_terms)[:5],
            })

        # Deduplicate overlapping spans (prefer longest span)
        spans.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
        filtered_spans = []
        last_end = -1
        for sp in spans:
            if sp["start"] >= last_end:
                filtered_spans.append(sp)
                last_end = sp["end"]

        return {
            "cleaned_text": cleaned_full,
            "skill_count": len(enriched),
            "skills": enriched,
            "spans": filtered_spans,
        }

    def evaluate_100_sample_benchmark(
        self,
        postings_df: pd.DataFrame,
        ground_truth_path: Optional[str] = None,
    ) -> Dict:
        """
        Evaluates the rule-based NLP skill extractor against the independent,
        human-audited 100-posting ground-truth benchmark (`nlp/ground_truth_100.json`),
        reporting micro/macro Precision, Recall, F1, hard-negative specificity,
        and concrete False Positive / False Negative error analysis.
        """
        if ground_truth_path is None:
            ground_truth_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ground_truth_100.json")

        with open(ground_truth_path, "r", encoding="utf-8") as f:
            gt_records = json.load(f)

        df_lookup = postings_df.copy()
        df_lookup["_jid_str"] = df_lookup["job_id"].astype(str)
        row_by_jid = {}
        for _, r in df_lookup.iterrows():
            jid = r["_jid_str"]
            if jid not in row_by_jid:
                row_by_jid[jid] = r

        tp_total, fp_total, fn_total = 0, 0, 0
        eval_rows = []
        fp_examples = []
        fn_examples = []
        nontech_fp_count = 0
        nontech_total = 0

        for gt in gt_records:
            jid = str(gt["job_id"])
            row = row_by_jid.get(jid)
            if row is None:
                continue

            raw_desc = row.get("desc_clean") if "desc_clean" in row else clean_html_text(row.get("description", ""))
            skills_desc = str(row.get("skills_desc", "")) if pd.notna(row.get("skills_desc")) else ""
            title = str(row.get("title", gt.get("job_title", "")))

            pred_items = self.extract_from_text(f"{title}. {raw_desc}", skills_desc)
            pred_set = {item["skill_name"] for item in pred_items}
            gt_set = set(gt["ground_truth_skills"])

            tp_set = pred_set & gt_set
            fp_set = pred_set - gt_set
            fn_set = gt_set - pred_set

            tp = len(tp_set)
            fp = len(fp_set)
            fn = len(fn_set)

            tp_total += tp
            fp_total += fp
            fn_total += fn

            if gt.get("stratum") == "nontech_hard_negative":
                nontech_total += 1
                if fp > 0:
                    nontech_fp_count += 1

            p_i = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
            r_i = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
            f1_i = (2 * p_i * r_i / (p_i + r_i)) if (p_i + r_i) > 0 else (1.0 if (tp + fp + fn) == 0 else 0.0)

            if fp_set and len(fp_examples) < 12:
                fp_examples.append({"job_id": jid, "job_title": title, "false_positives": sorted(fp_set)})
            if fn_set and len(fn_examples) < 12:
                fn_examples.append({"job_id": jid, "job_title": title, "false_negatives": sorted(fn_set)})

            eval_rows.append({
                "sample_id": int(gt["sample_id"]),
                "job_id": jid,
                "stratum": gt.get("stratum", "unknown"),
                "job_title": title[:100],
                "predicted_skills": ", ".join(sorted(pred_set)),
                "ground_truth_skills": ", ".join(sorted(gt_set)),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": round(p_i, 4),
                "recall": round(r_i, 4),
                "f1_score": round(f1_i, 4),
            })

        precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
        recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        macro_precision = float(np.mean([r["precision"] for r in eval_rows])) if eval_rows else 0.0
        macro_recall = float(np.mean([r["recall"] for r in eval_rows])) if eval_rows else 0.0
        macro_f1 = float(np.mean([r["f1_score"] for r in eval_rows])) if eval_rows else 0.0
        hard_neg_specificity = (
            (nontech_total - nontech_fp_count) / nontech_total if nontech_total > 0 else 1.0
        )

        return {
            "evaluation_mode": "independent_ground_truth_100",
            "sample_size": len(eval_rows),
            "true_positives": int(tp_total),
            "false_positives": int(fp_total),
            "false_negatives": int(fn_total),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "macro_precision": round(macro_precision, 4),
            "macro_recall": round(macro_recall, 4),
            "macro_f1_score": round(macro_f1, 4),
            "hard_negative_count": nontech_total,
            "hard_negative_clean_rate": round(hard_neg_specificity, 4),
            "false_positive_examples": fp_examples,
            "false_negative_examples": fn_examples,
            "samples": eval_rows,
        }
