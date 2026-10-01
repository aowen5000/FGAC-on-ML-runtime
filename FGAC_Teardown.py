# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,FGAC Teardown — Cleanup
# MAGIC %md
# MAGIC # FGAC Teardown
# MAGIC
# MAGIC This notebook removes all resources created by `FGAC_Setup`:
# MAGIC - Drops the row filter and column masks from the table
# MAGIC - Drops the UDFs
# MAGIC - Drops the table and schema
# MAGIC - Drops the catalog
# MAGIC - Deletes the account-level groups
# MAGIC
# MAGIC **Parameter:** `catalog_name` must match the value used during setup.

# COMMAND ----------

# DBTITLE 1,Configure Parameters
dbutils.widgets.text("catalog_name", "", "Catalog Name")
CATALOG = dbutils.widgets.get("catalog_name")
SCHEMA = "rls_demo"

assert CATALOG, "Please provide a catalog_name parameter"
print(f"Will tear down resources in: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# DBTITLE 1,Step 1: Remove Row Filter and Column Masks
# MAGIC %sql
# MAGIC -- Remove row filter
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees DROP ROW FILTER;
# MAGIC
# MAGIC -- Remove column masks
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees ALTER COLUMN ssn DROP MASK;
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees ALTER COLUMN salary DROP MASK;
# MAGIC ALTER TABLE ${catalog_name}.rls_demo.employees ALTER COLUMN email DROP MASK

# COMMAND ----------

# DBTITLE 1,Step 2: Drop UDFs
# MAGIC %sql
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.rls_demo.region_filter;
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.rls_demo.mask_ssn;
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.rls_demo.mask_salary;
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.rls_demo.mask_email

# COMMAND ----------

# DBTITLE 1,Step 3: Drop Table and Schema
# MAGIC %sql
# MAGIC DROP TABLE IF EXISTS ${catalog_name}.rls_demo.employees;
# MAGIC DROP SCHEMA IF EXISTS ${catalog_name}.rls_demo CASCADE

# COMMAND ----------

# DBTITLE 1,Step 4: Drop Catalog
# MAGIC %sql
# MAGIC DROP CATALOG IF EXISTS ${catalog_name} CASCADE

# COMMAND ----------

# DBTITLE 1,Step 5: Delete Account-Level Groups
import requests

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
host = ctx.apiUrl().get()
token = ctx.apiToken().get()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

for group_name in ["Upstart_ML_all"]:
    # Find the group by name
    resp = requests.get(
        f"{host}/api/2.0/account/scim/v2/Groups?filter=displayName eq \"{group_name}\"",
        headers=headers
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("totalResults", 0) > 0:
            group_id = data["Resources"][0]["id"]
            del_resp = requests.delete(
                f"{host}/api/2.0/account/scim/v2/Groups/{group_id}",
                headers=headers
            )
            if del_resp.status_code in [200, 204]:
                print(f"Deleted account group '{group_name}' (id: {group_id})")
            else:
                print(f"Error deleting '{group_name}': {del_resp.status_code} - {del_resp.text[:200]}")
        else:
            print(f"Account group '{group_name}' not found (already deleted?)")
    else:
        print(f"Error searching for '{group_name}': {resp.status_code}")

print("\nTeardown complete!")
