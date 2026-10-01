# Databricks notebook source
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
# MAGIC - **`Upstart_ML_restricted` members / others**: See only US-region rows (~69) with masked SSN, email, and salary
# MAGIC
# MAGIC **Parameter:** `catalog_name` — the catalog used in `FGAC_Setup`

# COMMAND ----------

# DBTITLE 1,Configure Parameters
dbutils.widgets.text("catalog_name", "", "Catalog Name")
CATALOG = dbutils.widgets.get("catalog_name")
assert CATALOG, "Please provide a catalog_name parameter"

print(f"Testing FGAC on: {CATALOG}.rls_demo.employees")
print(f"Current user: {spark.sql('SELECT current_user()').collect()[0][0]}")

# COMMAND ----------

# DBTITLE 1,Check Current User's Group Membership
membership = spark.sql("""
    SELECT 
        current_user() AS user,
        IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all') AS in_upstart_ml_all,
        IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_restricted') AS in_upstart_ml_restricted
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
# MAGIC --   Upstart_ML_all:        All 200 rows, raw SSN/email/salary
# MAGIC --   Upstart_ML_restricted: Only US rows (~69), masked SSN/email/salary
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

# DBTITLE 1,Table Security Metadata
# MAGIC %sql
# MAGIC -- Shows the row filter and column masks applied to the table
# MAGIC DESCRIBE EXTENDED ${catalog_name}.rls_demo.employees
