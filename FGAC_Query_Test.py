# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,FGAC Query Test — Row-Level Filters & Column Masks on ML Runtime
# MAGIC %md
# MAGIC # FGAC Query Test — Row-Level Filters & Column Masks on ML Runtime
# MAGIC
# MAGIC This notebook tests Row-Level Filters and Column Masks on the `employees` table.
# MAGIC
# MAGIC **Attach this notebook to the `FGAC-ML-Runtime-Test` cluster** (16.4 LTS ML) created by `Create_ML_Cluster`.
# MAGIC
# MAGIC **What to expect:**
# MAGIC - **`Upstart_ML_all` members**: See all 200 rows with full, unmasked data
# MAGIC - **Others**: See only US-region rows (~69) with masked SSN, email, and salary
# MAGIC
# MAGIC **Parameter:** `catalog_name` — the catalog used in `FGAC_Setup`

# COMMAND ----------

# DBTITLE 1,Configure Parameters
# An existing widget value is "sticky" (dbutils ignores the default on re-runs). Set
# DEFAULT_CATALOG to hardcode a default for interactive runs; if the widget is present but
# empty we force it in. Job runs inject a non-empty value via base_parameters, so the
# force branch is skipped there.
DEFAULT_CATALOG = ""  # optional: hardcode a default, e.g. "fevm_shared_catalog"

dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")
if DEFAULT_CATALOG and not dbutils.widgets.get("catalog_name").strip():
    dbutils.widgets.remove("catalog_name")
    dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")

CATALOG = dbutils.widgets.get("catalog_name").strip()
assert CATALOG, "Type a catalog into the 'Catalog Name' widget at the top, or set DEFAULT_CATALOG in this cell."

print(f"Testing FGAC on: {CATALOG}.rls_demo.employees")
print(f"Current user: {spark.sql('SELECT current_user()').collect()[0][0]}")

# COMMAND ----------

# DBTITLE 1,Check Current User's Group Membership
membership = spark.sql("""
    SELECT 
        current_user() AS user,
        IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all') AS in_upstart_ml_all
""")
membership.show(truncate=False)

row = membership.collect()[0]
if row.in_upstart_ml_all:
    print("You are in Upstart_ML_all -> you should see ALL 200 rows with UNMASKED data")
else:
    print("You are NOT in Upstart_ML_all -> you should see only US rows (~69) with MASKED data")

# COMMAND ----------

# DBTITLE 1,SELECT * — Full Table Query (Row Filters & Column Masks Applied)
# MAGIC %sql
# MAGIC -- This query demonstrates Row-Level Filters and Column Masks in action.
# MAGIC -- The results you see depend on your group membership:
# MAGIC --   Upstart_ML_all members: All 200 rows, raw SSN/email/salary
# MAGIC --   Others:                 Only US rows (~69), masked SSN/email/salary
# MAGIC
# MAGIC SELECT * FROM ${catalog_name}.rls_demo.employees

# COMMAND ----------

# DBTITLE 1,Row Count by Region (Verify Row-Level Filter)
# MAGIC %sql
# MAGIC -- If row filter is active, you should only see 'US' region
# MAGIC -- If you're in Upstart_ML_all, you'll see US, EU, and APAC
# MAGIC
# MAGIC SELECT region, COUNT(*) AS row_count
# MAGIC FROM ${catalog_name}.rls_demo.employees
# MAGIC GROUP BY region
# MAGIC ORDER BY region

# COMMAND ----------

# DBTITLE 1,Verify Column Masks (SSN, Email, Salary)
# MAGIC %sql
# MAGIC -- Check if sensitive columns are masked:
# MAGIC --   SSN:    Should show '***-**-XXXX' if masked
# MAGIC --   Email:  Should show '****@domain' if masked
# MAGIC --   Salary: Should show NULL if masked
# MAGIC
# MAGIC SELECT 
# MAGIC     employee_id,
# MAGIC     first_name,
# MAGIC     last_name,
# MAGIC     email,
# MAGIC     ssn,
# MAGIC     salary,
# MAGIC     department,
# MAGIC     region
# MAGIC FROM ${catalog_name}.rls_demo.employees
# MAGIC LIMIT 10

# COMMAND ----------

# DBTITLE 1,Summary Statistics (Salary Aggregation Test)
# MAGIC %sql
# MAGIC -- If column mask is active, salary is NULL and aggregations return NULL
# MAGIC -- If you're in Upstart_ML_all, you'll see actual statistics
# MAGIC
# MAGIC SELECT 
# MAGIC     COUNT(*) AS total_visible_rows,
# MAGIC     COUNT(salary) AS non_null_salary_count,
# MAGIC     ROUND(AVG(salary), 2) AS avg_salary,
# MAGIC     ROUND(MIN(salary), 2) AS min_salary,
# MAGIC     ROUND(MAX(salary), 2) AS max_salary,
# MAGIC     COUNT(DISTINCT region) AS distinct_regions,
# MAGIC     COUNT(DISTINCT department) AS distinct_departments
# MAGIC FROM ${catalog_name}.rls_demo.employees

# COMMAND ----------

# DBTITLE 1,Table Security Metadata (via information_schema)
# MAGIC %sql
# MAGIC -- DESCRIBE EXTENDED is not supported on dedicated (single-user) compute with
# MAGIC -- FGAC-protected tables until DBR 17.1+. Use information_schema instead.
# MAGIC
# MAGIC SELECT column_name, data_type, is_nullable, comment
# MAGIC FROM ${catalog_name}.information_schema.columns
# MAGIC WHERE table_schema = 'rls_demo' AND table_name = 'employees'
# MAGIC ORDER BY ordinal_position

# COMMAND ----------

# DBTITLE 1,Add Current User to Upstart_ML_all Group

# Add the current user to 'Upstart_ML_all' so they can see all 200 rows
# with unmasked SSN, email, and salary columns.
# Group management requires the SCIM API — there is no SQL equivalent.
# After running this cell, re-run cells 3–8 above to verify the change.

import requests, json

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST = ctx.apiUrl().get()
TOKEN = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Get current user email
me = spark.sql("SELECT current_user()").collect()[0][0]

# Look up account-level group and user IDs
ACCOUNT_SCIM = f"{HOST}/api/2.0/account/scim/v2"

grp_resp = requests.get(f"{ACCOUNT_SCIM}/Groups", headers=HEADERS,
                        params={"filter": 'displayName eq "Upstart_ML_all"'})
grp_resp.raise_for_status()
groups = grp_resp.json().get("Resources", [])
assert groups, "Group 'Upstart_ML_all' not found — run FGAC_Setup first"
group_id = groups[0]["id"]

usr_resp = requests.get(f"{ACCOUNT_SCIM}/Users", headers=HEADERS,
                        params={"filter": f'userName eq "{me}"'})
usr_resp.raise_for_status()
users = usr_resp.json().get("Resources", [])
assert users, f"User '{me}' not found in account SCIM"
user_id = users[0]["id"]

# Add user to group
patch_resp = requests.patch(
    f"{ACCOUNT_SCIM}/Groups/{group_id}",
    headers=HEADERS,
    json={
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "add", "path": "members",
                        "value": [{"value": user_id}]}],
    },
)
assert patch_resp.status_code in [200, 204], f"SCIM patch failed: {patch_resp.status_code} - {patch_resp.text[:200]}"

print(f"✅ Added '{me}' to 'Upstart_ML_all'")
print("\n⚠️  On dedicated (single-user) compute, group membership is cached at")
print("   cluster attach time. You MUST detach and reattach the cluster")
print("   (or restart it) for the change to take effect.")
print("\n⬆️  After reattaching, re-run cells 2–8 to see ALL 200 rows with unmasked data.")
