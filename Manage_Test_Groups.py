# Databricks notebook source
# DBTITLE 1,Manage Test Groups — Add/Remove Users for FGAC Demo
# MAGIC %md
# MAGIC # Manage Test Groups — Add/Remove Users for FGAC Demo
# MAGIC
# MAGIC Use this notebook to **add and remove users** from the two FGAC test groups:
# MAGIC
# MAGIC | Group | Access Level |
# MAGIC |---|---|
# MAGIC | `Upstart_ML_all` | Full access — sees all 200 rows, unmasked SSN/email/salary |
# MAGIC | `Upstart_ML_restricted` | Restricted — sees only US rows (~69), masked SSN/email/salary |
# MAGIC
# MAGIC **Demo workflow:**
# MAGIC 1. Add a user to `Upstart_ML_restricted` → have them run `FGAC_Query_Test` → observe masked/filtered data
# MAGIC 2. Move that user to `Upstart_ML_all` → re-run `FGAC_Query_Test` → observe full unmasked data
# MAGIC 3. Remove the user from both groups to reset
# MAGIC
# MAGIC > **Tip:** Users must detach and reattach their cluster (or restart it) after a group change for the new membership to take effect.

# COMMAND ----------

# DBTITLE 1,Helper Functions — SCIM API Utilities
import requests, json

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST = ctx.apiUrl().get()
TOKEN = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

ACCOUNT_GROUPS_API = f"{HOST}/api/2.0/account/scim/v2/Groups"
ACCOUNT_USERS_API = f"{HOST}/api/2.0/account/scim/v2/Users"

# ── Lookup helpers ──────────────────────────────────────────────

def get_group_id(group_name: str) -> str:
    """Return the account-level group ID for a given group name."""
    resp = requests.get(ACCOUNT_GROUPS_API,
                        headers=HEADERS,
                        params={"filter": f'displayName eq "{group_name}"'})
    resp.raise_for_status()
    resources = resp.json().get("Resources", [])
    assert resources, f"Group '{group_name}' not found"
    return resources[0]["id"]

def get_user_id(email: str) -> str:
    """Return the account-level user ID for a given email address."""
    resp = requests.get(ACCOUNT_USERS_API,
                        headers=HEADERS,
                        params={"filter": f'userName eq "{email}"'})
    resp.raise_for_status()
    resources = resp.json().get("Resources", [])
    assert resources, f"User '{email}' not found"
    return resources[0]["id"]

# ── Add / Remove ───────────────────────────────────────────────

def add_user_to_group(email: str, group_name: str):
    """Add a user to an account-level group."""
    group_id = get_group_id(group_name)
    user_id = get_user_id(email)
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{
            "op": "add",
            "path": "members",
            "value": [{"value": user_id}]
        }]
    }
    resp = requests.patch(f"{ACCOUNT_GROUPS_API}/{group_id}",
                          headers=HEADERS, json=payload)
    if resp.status_code in [200, 204]:
        print(f"  Added '{email}' to '{group_name}'")
    else:
        print(f"  Error adding '{email}' to '{group_name}': {resp.status_code} - {resp.text[:200]}")

def remove_user_from_group(email: str, group_name: str):
    """Remove a user from an account-level group."""
    group_id = get_group_id(group_name)
    user_id = get_user_id(email)
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{
            "op": "remove",
            "path": f'members[value eq "{user_id}"]'
        }]
    }
    resp = requests.patch(f"{ACCOUNT_GROUPS_API}/{group_id}",
                          headers=HEADERS, json=payload)
    if resp.status_code in [200, 204]:
        print(f"  Removed '{email}' from '{group_name}'")
    else:
        print(f"  Error removing '{email}' from '{group_name}': {resp.status_code} - {resp.text[:200]}")

# ── List members ───────────────────────────────────────────────

def list_group_members(group_name: str):
    """List all members of an account-level group."""
    group_id = get_group_id(group_name)
    resp = requests.get(f"{ACCOUNT_GROUPS_API}/{group_id}", headers=HEADERS)
    resp.raise_for_status()
    members = resp.json().get("members", [])
    if members:
        print(f"  Members of '{group_name}':")
        for m in members:
            print(f"    - {m.get('display', m.get('value', 'unknown'))}")
    else:
        print(f"  '{group_name}' has no members")
    return members

print("Helper functions loaded.")

# COMMAND ----------

# DBTITLE 1,List Current Group Members
print("=" * 50)
list_group_members("Upstart_ML_all")
print()
list_group_members("Upstart_ML_restricted")
print("=" * 50)

# COMMAND ----------

# DBTITLE 1,Add User to Upstart_ML_all (Full Access)
# ── EDIT THIS: set the email of the user to add ──
USER_EMAIL = "user@example.com"  # <-- change this

add_user_to_group(USER_EMAIL, "Upstart_ML_all")

# COMMAND ----------

# DBTITLE 1,Add User to Upstart_ML_restricted (Filtered/Masked Access)
# ── EDIT THIS: set the email of the user to add ──
USER_EMAIL = "user@example.com"  # <-- change this

add_user_to_group(USER_EMAIL, "Upstart_ML_restricted")

# COMMAND ----------

# DBTITLE 1,Remove User from Upstart_ML_all
# ── EDIT THIS: set the email of the user to remove ──
USER_EMAIL = "user@example.com"  # <-- change this

remove_user_from_group(USER_EMAIL, "Upstart_ML_all")

# COMMAND ----------

# DBTITLE 1,Remove User from Upstart_ML_restricted
# ── EDIT THIS: set the email of the user to remove ──
USER_EMAIL = "user@example.com"  # <-- change this

remove_user_from_group(USER_EMAIL, "Upstart_ML_restricted")

# COMMAND ----------

# DBTITLE 1,Move User: Restricted → Full Access
# ── EDIT THIS: set the email of the user to move ──
USER_EMAIL = "user@example.com"  # <-- change this

print(f"Moving '{USER_EMAIL}' from restricted to full access...")
remove_user_from_group(USER_EMAIL, "Upstart_ML_restricted")
add_user_to_group(USER_EMAIL, "Upstart_ML_all")
print("Done! User should reattach/restart their cluster for changes to take effect.")

# COMMAND ----------

# DBTITLE 1,Move User: Full Access → Restricted
# ── EDIT THIS: set the email of the user to move ──
USER_EMAIL = "user@example.com"  # <-- change this

print(f"Moving '{USER_EMAIL}' from full access to restricted...")
remove_user_from_group(USER_EMAIL, "Upstart_ML_all")
add_user_to_group(USER_EMAIL, "Upstart_ML_restricted")
print("Done! User should reattach/restart their cluster for changes to take effect.")

# COMMAND ----------

# DBTITLE 1,Remove User from All FGAC Groups (Reset)
# ── EDIT THIS: set the email of the user to remove from all groups ──
USER_EMAIL = "user@example.com"  # <-- change this

print(f"Removing '{USER_EMAIL}' from all FGAC groups...")
for group in ["Upstart_ML_all", "Upstart_ML_restricted"]:
    try:
        remove_user_from_group(USER_EMAIL, group)
    except Exception as e:
        print(f"  Skipped '{group}': {e}")
print("Done! User is now in neither group (will see restricted view by default).")

# COMMAND ----------

# DBTITLE 1,Bulk Add Multiple Users
# ── EDIT THIS: set the list of emails and target group ──
USER_EMAILS = [
    "user1@example.com",
    "user2@example.com",
    "user3@example.com",
]
TARGET_GROUP = "Upstart_ML_restricted"  # or "Upstart_ML_all"

print(f"Adding {len(USER_EMAILS)} users to '{TARGET_GROUP}'...")
for email in USER_EMAILS:
    try:
        add_user_to_group(email, TARGET_GROUP)
    except Exception as e:
        print(f"  Error for '{email}': {e}")
print("Done!")
