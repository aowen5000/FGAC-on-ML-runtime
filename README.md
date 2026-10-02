# Fine-Grained Access Control (FGAC) on ML Runtime

A deployable test environment for **Row-Level Filters** and **Column Masks** in Databricks Unity Catalog.

> **Read-only project.** This repo is shared as a reference artifact and is not accepting
> external contributions. Issues are disabled and pull requests will not be merged. See
> [CONTRIBUTING.md](CONTRIBUTING.md). You are welcome to fork and adapt it for your own use.

## What This Creates

| Resource | Details |
|---|---|
| Schema | `<your_catalog>.rls_demo` (created inside an existing catalog you provide) |
| Table | `<your_catalog>.rls_demo.employees` — 200 rows of Faker-generated employee data |
| Row Filter | `region_filter` — restricts non-privileged users to US-region rows only |
| Column Masks | `mask_ssn` (last 4 digits), `mask_salary` (NULL), `mask_email` (redacted username) |
| Group | `Upstart_ML_all` (full access — members bypass all restrictions) |
| Grants | USE CATALOG, USE SCHEMA, SELECT, EXECUTE on UDFs for `Upstart_ML_all` |

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

## How the Group Works

- **`Upstart_ML_all`**: Members see all 200 rows with full, unmasked data. The UDFs check `IS_ACCOUNT_GROUP_MEMBER('Upstart_ML_all')` and bypass all restrictions.
- Users **not** in the group see only US-region rows (~69 of 200) with masked SSN, email, and salary values.

## Required Permissions

The deploying user needs **all** of the following:

### Unity Catalog Permissions

You must supply an **existing** catalog via `catalog_name`; the repo does not create it.

| Permission | Securable | Why |
|---|---|---|
| `USE CATALOG` | Target catalog | Navigate into the existing catalog |
| `CREATE SCHEMA` | Target catalog | Create the `rls_demo` schema |
| `CREATE TABLE` | `<catalog>.rls_demo` schema | Create the `employees` table |
| `CREATE FUNCTION` | `<catalog>.rls_demo` schema | Create row filter and column mask UDFs |
| `GRANT` privilege | Target catalog, schema, table, functions | Grant `USE CATALOG`, `USE SCHEMA`, `SELECT`, `EXECUTE` to `Upstart_ML_all` |

> **Tip:** Being the owner of the target catalog (or a metastore admin) satisfies all of the above.

> **No workspace-default-catalog dependency.** Each notebook runs `USE CATALOG <your_catalog>`
> after resolving `catalog_name`, so every operation, including applying and evaluating row
> filters / column masks on dedicated (single-user) compute, resolves against the catalog you
> provide. The demo does not rely on the workspace default catalog setting.

### Account-Level Permissions

| Permission | Why |
|---|---|
| **Account admin** or **Group admin** | Create account-level group (`Upstart_ML_all`) via SCIM API |
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

Set a variable on the command line with `--var="catalog_name=your_catalog"`, or once for
the whole session via the environment: `export BUNDLE_VAR_catalog_name=your_catalog`.

### Bundle Targets

| Target | Mode | Use Case |
|---|---|---|
| `dev` | development | Local testing (default) |
| `staging` | default | Pre-production validation |
| `prod` | production | Customer-facing demo environment |

## Deployment with Declarative Automation Bundles (DAB)

### Option A: Deploy via CLI (recommended)

The bundle commands below authenticate with the CLI profile named by `-p`. Swap
`fgac-demo` for your own profile name, or omit `-p` entirely to use your `DEFAULT`
profile. Setting `BUNDLE_VAR_catalog_name` once means you don't repeat `--var=...` on
every command.

```bash
# 1. Clone the repo
git clone https://github.com/alex-owen_data/FGAC-on-ML-runtime.git
cd FGAC-on-ML-runtime

# 2. Configure a Databricks CLI profile (skip if you already have one)
databricks configure --profile fgac-demo

# 3. Point the bundle at your catalog once (used by every command below)
export BUNDLE_VAR_catalog_name=your_catalog

# 4. Validate the bundle
databricks bundle validate --target dev -p fgac-demo

# 5. Deploy all resources (ML cluster + jobs)
databricks bundle deploy --target dev -p fgac-demo

# 6. Run the setup job to create schema, table, UDFs, group, and grants
databricks bundle run fgac_setup --target dev -p fgac-demo

# 7. Verify FGAC: open the FGAC_Query_Test notebook, attach it to the
#    FGAC-ML-Runtime-Test cluster, and Run All (see note below).
#    It is run interactively, not as a job.
```

> **`FGAC_Query_Test` is run interactively, not as a job.** The test demonstrates how
> *different users* see different data based on group membership, so each person must run
> it as themselves by attaching to the `FGAC-ML-Runtime-Test` cluster. A job would always
> run as one identity and could not show that difference, which is why it is deliberately
> not defined in `resources/fgac_jobs.yml`.

> **The bundle creates the ML cluster for you.** `databricks bundle deploy` provisions
> the `FGAC-ML-Runtime-Test` cluster from `resources/fgac_cluster.yml`. Do **not** run the
> `Create_ML_Cluster` notebook on this path, it would create a duplicate cluster.

#### Deploy and run in one command

To deploy and execute in a single line, chain the commands with `&&` (each step runs only
if the previous one succeeded):

```bash
databricks bundle deploy --target dev --var="catalog_name=<your_catalog>" -p fgac-test && \
databricks bundle run fgac_setup --target dev --var="catalog_name=<your_catalog>" -p fgac-test
```

What it does, in order:

1. **`bundle deploy`** uploads the notebooks and creates the ML cluster and the jobs in
   the workspace (in `dev` mode they are prefixed with `[dev <your_username>]`). This only
   provisions the resources; it does not run anything.
2. **`bundle run fgac_setup`** starts the cluster, then creates the `rls_demo` schema,
   the `employees` table, the row-filter/column-mask UDFs, the `Upstart_ML_all` account
   group, and the grants, all inside `<your_catalog>`.

Then verify interactively: open `FGAC_Query_Test`, attach it to the `FGAC-ML-Runtime-Test`
cluster, and Run All. It is not part of this chain because it is run per-user, not as a job.

Because of the `&&`, if any step fails the chain stops. For example, if your identity
lacks `CREATE SCHEMA` on `<your_catalog>`, `fgac_setup` fails. Pass `--var="catalog_name=..."`
on every command (as above), or `export BUNDLE_VAR_catalog_name=<your_catalog>` once and
drop the `--var` flags.

### Option B: Manual deployment (no CLI)

Use this path only if you are not deploying with the CLI.

1. Import this repo into your Databricks workspace as a Git folder
2. Open `FGAC_Setup` notebook, set `catalog_name`, and Run All
3. Open `Create_ML_Cluster` notebook and Run All to provision the ML cluster (CLI users skip this, the bundle already created it)
4. Open `FGAC_Query_Test` notebook, **attach it to the `FGAC-ML-Runtime-Test` cluster**, set `catalog_name`, and Run All
5. Open `Manage_Test_Groups` to add test users to `Upstart_ML_all`
6. Have those users run `FGAC_Query_Test` on the ML cluster to observe the access differences

### Teardown

Teardown removes only the `rls_demo` schema and its contents (`DROP SCHEMA ... CASCADE`)
plus the account-level group. The **catalog you provided is left intact.**

```bash
# Remove FGAC resources (schema, table, UDFs, group) — catalog is left intact
databricks bundle run fgac_teardown --target dev -p fgac-demo

# Remove deployed bundle resources (cluster, jobs) from the workspace
databricks bundle destroy --target dev -p fgac-demo
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
3. Run All cells — this removes the row filter, column masks, UDFs, table, the `rls_demo` schema, and the group (the catalog you provided is left intact)
4. Manually terminate or delete the ML cluster from the Compute page

## Demo Walkthrough

After `fgac_setup` has run, you see FGAC in action by running the **`FGAC_Query_Test`
notebook manually**. It is deliberately not a job, because the whole point is that
*different users* see different data, so each person runs it as themselves.

### How to run FGAC_Query_Test (do this manually)

1. In the workspace, open the **`FGAC_Query_Test`** notebook (under your bundle folder,
   or import it from this repo).
2. **Attach it to the `FGAC-ML-Runtime-Test` cluster** (top-right compute selector). It
   must run on that dedicated ML cluster, not serverless or another cluster.
3. In the **`catalog_name`** widget at the top, enter the catalog you deployed into
   (e.g. `amitabh_arora_catalog`).
4. Click **Run All**. The notebook prints your group membership, then runs the queries so
   you can see the row filter and column masks for yourself.

### 1. Show restricted access
- As a user who is **not** in `Upstart_ML_all`, run `FGAC_Query_Test` as above.
- You'll see only US rows (~69) with masked SSN (`***-**-XXXX`), email (`****@domain`), and salary (`NULL`).

### 2. Show full access
- Use `Manage_Test_Groups` to add the user to `Upstart_ML_all`.
- The user **detaches and reattaches** (or restarts) the `FGAC-ML-Runtime-Test` cluster, then re-runs `FGAC_Query_Test`.
- They'll now see all 200 rows with raw, unmasked data.

### 3. Reset
- Use `Manage_Test_Groups` to remove the user from `Upstart_ML_all`.
- After reattaching the cluster, they revert to the restricted view (default for non-members).

> **Note:** Group membership changes require the user to detach and reattach their cluster
> (or restart it) before taking effect, because membership is cached at cluster attach time.
