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
# MAGIC - Drops the table and the `rls_demo` schema
# MAGIC - Deletes the account-level groups
# MAGIC
# MAGIC The **catalog you provided is left intact** — this notebook only removes the
# MAGIC `rls_demo` schema and its contents, never the catalog itself.
# MAGIC
# MAGIC **Parameter:** `catalog_name` must match the value used during setup.

# COMMAND ----------

# DBTITLE 1,Create Catalog Widget
# Create the widget in its own cell so the widget panel always renders, even on the first
# run. (If widget creation shared a cell with the assert below, a failed assert on the first
# run would stop the cell before the widget appeared.)
# An existing widget value is "sticky" (dbutils ignores the default on re-runs). Set
# DEFAULT_CATALOG to hardcode a default for interactive runs; if the widget is present but
# empty we force it in. Job runs inject a non-empty value via base_parameters, so the
# force branch is skipped there.
DEFAULT_CATALOG = ""  # optional: hardcode a default, e.g. "catalog"

dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")
if DEFAULT_CATALOG and not dbutils.widgets.get("catalog_name").strip():
    dbutils.widgets.remove("catalog_name")
    dbutils.widgets.text("catalog_name", DEFAULT_CATALOG, "Catalog Name")

# COMMAND ----------

# DBTITLE 1,Read and Validate Catalog
CATALOG = dbutils.widgets.get("catalog_name").strip()
SCHEMA = "rls_demo"

assert CATALOG, "Type a catalog into the 'Catalog Name' widget at the top, or set DEFAULT_CATALOG in the previous cell."

# Pin the session to this catalog so dropping the FGAC objects on dedicated compute
# resolves against it, not the workspace default catalog.
spark.sql(f"USE CATALOG {CATALOG}")
print(f"Will tear down resources in: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# DBTITLE 1,Step 1: Remove Row Filter and Column Masks
# Make teardown safely re-runnable. If the table or its policies are already gone (for
# example setup never finished, or teardown was run twice), these ALTERs would otherwise
# error. Dropping policies IS allowed on dedicated (single-user) compute, so attempt each
# one and swallow the "nothing to drop" case. The real cleanup is DROP SCHEMA ... CASCADE
# in Step 3, so a failure here is not fatal.
FQN = f"{CATALOG}.{SCHEMA}.employees"
for stmt in [
    f"ALTER TABLE {FQN} DROP ROW FILTER",
    f"ALTER TABLE {FQN} ALTER COLUMN ssn DROP MASK",
    f"ALTER TABLE {FQN} ALTER COLUMN salary DROP MASK",
    f"ALTER TABLE {FQN} ALTER COLUMN email DROP MASK",
]:
    try:
        spark.sql(stmt)
        print(f"OK: {stmt}")
    except Exception as e:
        print(f"  (nothing to drop) {str(e)[:100]}")

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

# DBTITLE 1,Step 4: Delete Account-Level Groups
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
