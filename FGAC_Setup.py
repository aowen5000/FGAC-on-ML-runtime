# Databricks notebook source
# DBTITLE 1,FGAC on ML Runtime — Setup
# MAGIC %md
# MAGIC # Fine-Grained Access Control (FGAC) on ML Runtime
# MAGIC
# MAGIC This notebook sets up a complete test environment for **Row-Level Filters** and **Column Masks** in Unity Catalog.
# MAGIC
# MAGIC **What it creates:**
# MAGIC 1. A schema (`rls_demo`) inside the catalog you provide
# MAGIC 2. An `employees` table with 200 rows of realistic Faker-generated data
# MAGIC 3. SQL UDFs for row filtering and column masking
# MAGIC 4. An account-level group: `Upstart_ML_all` (full access — members bypass all restrictions)
# MAGIC 5. All necessary grants (USE CATALOG, USE SCHEMA, SELECT, EXECUTE)
# MAGIC
# MAGIC **Parameters:**
# MAGIC - `catalog_name`: An **existing** Unity Catalog catalog to use. It must already exist and you must have `USE CATALOG` and `CREATE SCHEMA` on it. This notebook does not create the catalog.

# COMMAND ----------

# DBTITLE 1,Configure Parameters
# Catalog comes from the `catalog_name` widget (interactive runs) or from the job's
# base_parameters (job runs). An existing widget value is "sticky": dbutils ignores the
# default on re-runs, so a value typed once (or left empty) persists. To make a hardcoded
# default actually apply, set DEFAULT_CATALOG below; if the widget is present but empty we
# force the default in. Job runs inject a non-empty value, so that branch is skipped.
DEFAULT_CATALOG = ""  # optional: hardcode a default, e.g. "fevm_shared_catalog"

dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")
if DEFAULT_CATALOG and not dbutils.widgets.get("catalog_name").strip():
    dbutils.widgets.remove("catalog_name")
    dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")

CATALOG = dbutils.widgets.get("catalog_name").strip()
SCHEMA = "rls_demo"
TABLE_NAME = "employees"
FQN = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"

assert CATALOG, "Type a catalog into the 'Catalog Name' widget at the top, or set DEFAULT_CATALOG in this cell."
print(f"Using catalog: {CATALOG}")
print(f"Full table name: {FQN}")

# COMMAND ----------

# DBTITLE 1,Available Catalogs (reference — pick one for the catalog_name widget)
# Lists the catalogs you can see in this workspace. Use one of these names in the
# `catalog_name` widget above. You need USE CATALOG + CREATE SCHEMA on the one you pick.
spark.sql("SHOW CATALOGS").display()

# COMMAND ----------

# DBTITLE 1,Step 1: Validate Catalog and Create Schema
# The catalog must already exist and you must have USE CATALOG + CREATE SCHEMA on it.
# This notebook does NOT create the catalog.
found = spark.sql(f"SHOW CATALOGS LIKE '{CATALOG}'").collect()
assert found, (
    f"Catalog '{CATALOG}' not found or not accessible. "
    f"Provide an existing catalog you can use (you need USE CATALOG and CREATE SCHEMA on it), "
    f"then re-run."
)
print(f"Catalog {CATALOG} found")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"Schema {CATALOG}.{SCHEMA} created (or already exists)")

# COMMAND ----------

# DBTITLE 1,Step 2: Install Faker
# MAGIC %pip install faker -q

# COMMAND ----------

# DBTITLE 1,Restart Python after pip install
# MAGIC %restart_python

# COMMAND ----------

# DBTITLE 1,Re-read parameters after restart
CATALOG = dbutils.widgets.get("catalog_name").strip()
SCHEMA = "rls_demo"
TABLE_NAME = "employees"
FQN = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"
print(f"Restored parameters — target table: {FQN}")

# COMMAND ----------

# DBTITLE 1,Step 3: Generate Faker Data and Create Table
from faker import Faker
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, DateType
import random

fake = Faker()
Faker.seed(42)
random.seed(42)

departments = ["Engineering", "Sales", "Marketing", "Finance", "HR"]
regions = ["US", "EU", "APAC"]

rows = []
for i in range(200):
    rows.append((
        i + 1,
        fake.first_name(),
        fake.last_name(),
        fake.email(),
        fake.ssn(),
        fake.phone_number(),
        random.choice(departments),
        random.choice(regions),
        round(random.uniform(50000, 200000), 2),
        fake.date_of_birth(minimum_age=22, maximum_age=65),
        fake.address().replace("\n", ", ")
    ))

schema = StructType([
    StructField("employee_id", IntegerType(), False),
    StructField("first_name", StringType(), False),
    StructField("last_name", StringType(), False),
    StructField("email", StringType(), False),
    StructField("ssn", StringType(), False),
    StructField("phone", StringType(), False),
    StructField("department", StringType(), False),
    StructField("region", StringType(), False),
    StructField("salary", DoubleType(), False),
    StructField("date_of_birth", DateType(), False),
    StructField("address", StringType(), False),
])

df = spark.createDataFrame(rows, schema)
df.write.mode("overwrite").saveAsTable(FQN)
print(f"Table {FQN} created with {df.count()} rows")
df.show(5, truncate=False)

# COMMAND ----------

# DBTITLE 1,Step 4: Create Row Filter UDF
# MAGIC %sql
# MAGIC -- Row filter: Upstart_ML_all members see all rows, others see only US region
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.rls_demo.region_filter(region_val STRING)
# MAGIC RETURNS BOOLEAN
# MAGIC COMMENT 'Row filter: Upstart_ML_all sees all rows, others see only US region'
# MAGIC RETURN
# MAGIC   IF(IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all'), true, region_val = 'US')

# COMMAND ----------

# DBTITLE 1,Step 5: Create Column Mask UDFs
# MAGIC %sql
# MAGIC -- Mask SSN: show only last 4 digits for non-privileged users
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.rls_demo.mask_ssn(ssn_val STRING)
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Column mask: Upstart_ML_all sees raw SSN, others see last 4 digits only'
# MAGIC RETURN
# MAGIC   IF(IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all'), ssn_val, CONCAT('***-**-', RIGHT(ssn_val, 4)));
# MAGIC
# MAGIC -- Mask salary: NULL for non-privileged users
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.rls_demo.mask_salary(salary_val DOUBLE)
# MAGIC RETURNS DOUBLE
# MAGIC COMMENT 'Column mask: Upstart_ML_all sees raw salary, others see NULL'
# MAGIC RETURN
# MAGIC   IF(IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all'), salary_val, NULL);
# MAGIC
# MAGIC -- Mask email: redact username portion
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.rls_demo.mask_email(email_val STRING)
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Column mask: Upstart_ML_all sees raw email, others see redacted'
# MAGIC RETURN
# MAGIC   IF(IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all'), email_val, CONCAT('****@', SPLIT(email_val, '@')[1]))

# COMMAND ----------

# DBTITLE 1,Step 6: Apply Row Filter and Column Masks to Table
# MAGIC %sql
# MAGIC -- Apply row-level filter on the region column
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees
# MAGIC SET ROW FILTER ${catalog_name}.rls_demo.region_filter ON (region);
# MAGIC
# MAGIC -- Apply column mask on SSN
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees
# MAGIC ALTER COLUMN ssn SET MASK ${catalog_name}.rls_demo.mask_ssn;
# MAGIC
# MAGIC -- Apply column mask on salary
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees
# MAGIC ALTER COLUMN salary SET MASK ${catalog_name}.rls_demo.mask_salary;
# MAGIC
# MAGIC -- Apply column mask on email
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees
# MAGIC ALTER COLUMN email SET MASK ${catalog_name}.rls_demo.mask_email

# COMMAND ----------

# DBTITLE 1,Step 7: Create Account-Level Groups
import requests

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
host = ctx.apiUrl().get()
token = ctx.apiToken().get()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

for group_name in ["Upstart_ML_all"]:
    payload = {
        "displayName": group_name,
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    }
    resp = requests.post(
        f"{host}/api/2.0/account/scim/v2/Groups",
        headers=headers,
        json=payload
    )
    if resp.status_code in [200, 201]:
        data = resp.json()
        print(f"Created account group '{group_name}' (id: {data.get('id', 'N/A')})")
    elif resp.status_code == 409:
        print(f"Account group '{group_name}' already exists")
    else:
        print(f"Error creating '{group_name}': {resp.status_code} - {resp.text[:200]}")

# COMMAND ----------

# DBTITLE 1,Step 8: Grant Permissions to Both Groups
CATALOG = dbutils.widgets.get("catalog_name").strip()
SCHEMA = "rls_demo"

grants = [
    f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `Upstart_ML_all`",
    f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `Upstart_ML_all`",
    f"GRANT SELECT ON TABLE {CATALOG}.{SCHEMA}.employees TO `Upstart_ML_all`",
    f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.region_filter TO `Upstart_ML_all`",
    f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.mask_ssn TO `Upstart_ML_all`",
    f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.mask_salary TO `Upstart_ML_all`",
    f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.mask_email TO `Upstart_ML_all`",
]

success = 0
for stmt in grants:
    try:
        spark.sql(stmt)
        print(f"OK: {stmt}")
        success += 1
    except Exception as e:
        print(f"FAIL: {stmt}\n  Error: {str(e)[:200]}\n")

print(f"\nCompleted: {success}/{len(grants)} grants succeeded")

# COMMAND ----------

# DBTITLE 1,Step 9: Verify Setup
CATALOG = dbutils.widgets.get("catalog_name").strip()
FQN = f"{CATALOG}.rls_demo.employees"

print(f"Current user: {spark.sql('SELECT current_user()').collect()[0][0]}")
print(f"Visible rows (filtered): {spark.sql(f'SELECT COUNT(*) FROM {FQN}').collect()[0][0]}")
print(f"Total rows in table: 200")
print()
print("Sample data (as current user — observe masking in effect):")
spark.sql(f"""
    SELECT employee_id, first_name, last_name, email, ssn, department, region, salary
    FROM {FQN} LIMIT 10
""").show(truncate=False)

# COMMAND ----------

# DBTITLE 1,Verify Table Security Metadata
# MAGIC %sql
# MAGIC DESCRIBE EXTENDED ${catalog_name}.rls_demo.employees
