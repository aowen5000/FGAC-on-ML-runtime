# Fine-Grained Access Control (FGAC) on ML Runtime

A deployable test environment for **Row-Level Filters** and **Column Masks** in Databricks Unity Catalog.

## What This Creates

| Resource | Details |
|---|---|
| Schema | `<your_catalog>.rls_demo` |
| Table | `<your_catalog>.rls_demo.employees` — 200 rows of Faker-generated employee data |
| Row Filter | `region_filter` — restricts non-privileged users to US-region rows only |
| Column Masks | `mask_ssn` (last 4 digits), `mask_salary` (NULL), `mask_email` (redacted username) |
| Groups | `Upstart_ML_all` (full access) and `Upstart_ML_restricted` (filtered/masked view) |
| Grants | USE CATALOG, USE SCHEMA, SELECT, EXECUTE on UDFs for both groups |

## Employee Table Schema

| Column | Type | Security |
|---|---|---|
| `employee_id` | INT | — |
| `first_name` | STRING | — |
| `last_name` | STRING | — |
| `email` | STRING | Column mask (redacted username) |
| `ssn` | STRING | Column mask (last 4 digits) |
| `phone` | STRING | — |
| `department` | STRING | — |
| `region` | STRING | Row filter (US only for restricted users) |
| `salary` | DOUBLE | Column mask (NULL for restricted users) |
| `date_of_birth` | DATE | — |
| `address` | STRING | — |

## How Groups Work

- **`Upstart_ML_all`**: Members see all 200 rows with full, unmasked data. The UDFs check `IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all')` and bypass all restrictions.
- **`Upstart_ML_restricted`**: Members see only US-region rows (~69 of 200) with masked SSN, email, and salary values.
- Users not in either group behave like `Upstart_ML_restricted` (restricted view).

## Prerequisites

- Databricks workspace with Unity Catalog enabled
- An existing catalog where you have `CREATE SCHEMA` privilege
- Permission to create account-level groups (account admin or group admin)
- Serverless compute or DBR 15.4+

## Repository Contents

| Notebook | Purpose |
|---|---|
| `FGAC_Setup` | Creates schema, table, UDFs, groups, and grants (run first) |
| `Create_ML_Cluster` | Provisions a single-node 16.4 LTS ML cluster for testing |
| `FGAC_Query_Test` | SELECT * and validation queries — attach to the ML cluster |
| `Manage_Test_Groups` | Add/remove users from test groups to demo access differences |
| `FGAC_Teardown` | Removes all resources created by setup |

## Quick Start

1. Import this repo into your Databricks workspace as a Git folder
2. Open `FGAC_Setup` notebook, set `catalog_name`, and Run All
3. Open `Create_ML_Cluster` notebook and Run All to provision the ML cluster
4. Open `FGAC_Query_Test` notebook, **attach it to the `FGAC-ML-Runtime-Test` cluster**, set `catalog_name`, and Run All
5. Open `Manage_Test_Groups` to add test users to `Upstart_ML_all` or `Upstart_ML_restricted`
6. Have those users run `FGAC_Query_Test` on the ML cluster to observe the access differences

## ML Cluster Details

The `Create_ML_Cluster` notebook provisions:
- **Runtime**: 16.4 LTS ML (includes Apache Spark 3.5.2, Scala 2.12)
- **Node**: `i3.xlarge` single-node (31 GB RAM, 4 cores) — configurable via widget
- **Access Mode**: Single User
- **Auto-terminate**: 60 minutes

## Cleanup

1. Open `FGAC_Teardown` notebook
2. Set the `catalog_name` widget to the same catalog used during setup
3. Run All cells — this removes the row filter, column masks, UDFs, table, schema, and groups
4. Manually terminate or delete the ML cluster from the Compute page

## Demo Walkthrough

### 1. Show restricted access
- Use `Manage_Test_Groups` to add a demo user to `Upstart_ML_restricted`
- Have them attach to the ML cluster, open `FGAC_Query_Test`, set `catalog_name`, and Run All
- They'll see only US rows (~69) with masked SSN (`***-**-XXXX`), email (`****@domain`), and salary (`NULL`)

### 2. Show full access
- Use `Manage_Test_Groups` to move the user from `Upstart_ML_restricted` to `Upstart_ML_all`
- User restarts/reattaches their cluster, re-runs `FGAC_Query_Test`
- They'll now see all 200 rows with raw, unmasked data

### 3. Reset
- Use `Manage_Test_Groups` to remove the user from all groups
- They'll revert to the restricted view (default for non-members)

> **Note:** Group membership changes require the user to detach and reattach their cluster (or restart it) before taking effect.
