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

## Required Permissions

The deploying user needs **all** of the following:

### Unity Catalog Permissions

| Permission | Securable | Why |
|---|---|---|
| `USE CATALOG` | Target catalog | Navigate into the catalog |
| `CREATE SCHEMA` | Target catalog | Create the `rls_demo` schema |
| `CREATE TABLE` | `<catalog>.rls_demo` schema | Create the `employees` table |
| `CREATE FUNCTION` | `<catalog>.rls_demo` schema | Create row filter and column mask UDFs |
| `GRANT` privilege | Target catalog, schema, table, functions | Grant `USE CATALOG`, `USE SCHEMA`, `SELECT`, `EXECUTE` to the two groups |

> **Tip:** Catalog owner or metastore admin satisfies all of the above.

### Account-Level Permissions

| Permission | Why |
|---|---|
| **Account admin** or **Group admin** | Create account-level groups (`Upstart_ML_all`, `Upstart_ML_restricted`) via SCIM API |
| Account SCIM API access | Add/remove users from groups (`Manage_Test_Groups` notebook) |

### Workspace Permissions

| Permission | Why |
|---|---|
| `Allow unrestricted cluster creation` OR cluster policy access | Provision the 16.4 LTS ML single-node cluster |
| Workspace access for demo users | Users in the test groups need workspace access to run the query notebook |

### Declarative Automation Bundle (DAB) Deployment

| Permission | Why |
|---|---|
| Databricks CLI installed (v0.218+) | Run `bundle deploy` / `bundle run` commands |
| Workspace token or OAuth configured | CLI authentication to the target workspace |
| `CAN_MANAGE` on deployed jobs | Automatically granted to the deploying user |

## Repository Structure

```
FGAC-on-ML-runtime/
├── databricks.yml              # DAB bundle config (variables, targets)
├── resources/
│   ├── fgac_cluster.yml        # ML cluster definition (16.4 LTS, i3.xlarge)
│   └── fgac_jobs.yml           # Job definitions for all notebooks
├── FGAC_Setup.py               # Creates schema, table, UDFs, groups, grants
├── Create_ML_Cluster.py        # Provisions the ML cluster via API
├── FGAC_Query_Test.py          # SELECT * and validation queries
├── Manage_Test_Groups.py       # Add/remove users from test groups
├── FGAC_Teardown.py            # Removes all resources
└── README.md
```

### Bundle Variables

| Variable | Description | Default |
|---|---|---|
| `catalog_name` | Unity Catalog catalog to deploy into | _(required)_ |
| `node_type` | EC2 instance type for the ML cluster | `i3.xlarge` |

### Bundle Targets

| Target | Mode | Use Case |
|---|---|---|
| `dev` | development | Local testing (default) |
| `staging` | default | Pre-production validation |
| `prod` | production | Customer-facing demo environment |

## Deployment with Declarative Automation Bundles (DAB)

### Option A: Deploy via CLI (recommended)

```bash
# 1. Clone the repo
git clone https://github.com/alex-owen_data/FGAC-on-ML-runtime.git
cd FGAC-on-ML-runtime

# 2. Configure your Databricks CLI profile (if not already done)
databricks configure --profile fgac-demo

# 3. Validate the bundle
databricks bundle validate --target dev -var="catalog_name=your_catalog"

# 4. Deploy all resources (cluster + jobs)
databricks bundle deploy --target dev -var="catalog_name=your_catalog"

# 5. Run the setup job to create schema, table, UDFs, groups, and grants
databricks bundle run fgac_setup --target dev

# 6. Run the query test to verify FGAC is working
databricks bundle run fgac_query_test --target dev
```

### Option B: Manual deployment (no CLI)

1. Import this repo into your Databricks workspace as a Git folder
2. Open `FGAC_Setup` notebook, set `catalog_name`, and Run All
3. Open `Create_ML_Cluster` notebook and Run All to provision the ML cluster
4. Open `FGAC_Query_Test` notebook, **attach it to the `FGAC-ML-Runtime-Test` cluster**, set `catalog_name`, and Run All
5. Open `Manage_Test_Groups` to add test users to `Upstart_ML_all` or `Upstart_ML_restricted`
6. Have those users run `FGAC_Query_Test` on the ML cluster to observe the access differences

### Teardown

```bash
# Remove FGAC resources (table, schema, UDFs, groups)
databricks bundle run fgac_teardown --target dev

# Remove deployed bundle resources (cluster, jobs) from the workspace
databricks bundle destroy --target dev
```

Or manually: run `FGAC_Teardown` notebook, then delete the ML cluster from the Compute page.

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
