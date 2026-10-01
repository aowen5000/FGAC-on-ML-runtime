# Databricks notebook source
# DBTITLE 1,Create ML Cluster for FGAC Testing
# MAGIC %md
# MAGIC # Create ML Cluster for FGAC Testing
# MAGIC
# MAGIC This notebook provisions a **single-node ML cluster** running the latest ML LTS runtime for testing Row-Level Filters and Column Masks.
# MAGIC
# MAGIC **What it creates:**
# MAGIC - Single-node cluster with **16.4 LTS ML** runtime (includes Apache Spark 3.5.2)
# MAGIC - `i3.xlarge` node type (31 GB RAM, 4 cores) — configurable
# MAGIC - Single User access mode (required for ML runtime)
# MAGIC - Auto-terminates after 60 minutes of inactivity
# MAGIC
# MAGIC **Parameters:**
# MAGIC - `cluster_name`: Name for the cluster (default: `FGAC-ML-Runtime-Test`)
# MAGIC - `node_type`: EC2 instance type (default: `i3.xlarge`)
# MAGIC
# MAGIC > **Note**: Run this on serverless compute or any existing cluster. The cluster it creates is a separate resource.

# COMMAND ----------

# DBTITLE 1,Configure Parameters
dbutils.widgets.text("cluster_name", "FGAC-ML-Runtime-Test", "Cluster Name")
dbutils.widgets.text("node_type", "i3.xlarge", "Node Type")

CLUSTER_NAME = dbutils.widgets.get("cluster_name")
NODE_TYPE = dbutils.widgets.get("node_type")

print(f"Cluster name: {CLUSTER_NAME}")
print(f"Node type: {NODE_TYPE}")

# COMMAND ----------

# DBTITLE 1,Step 1: Create the ML Cluster
import requests, json, time

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
host = ctx.apiUrl().get()
token = ctx.apiToken().get()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

CLUSTER_NAME = dbutils.widgets.get("cluster_name")
NODE_TYPE = dbutils.widgets.get("node_type")

cluster_config = {
    "cluster_name": CLUSTER_NAME,
    "spark_version": "16.4.x-cpu-ml-scala2.12",
    "node_type_id": NODE_TYPE,
    "num_workers": 0,
    "spark_conf": {
        "spark.databricks.cluster.profile": "singleNode",
        "spark.master": "local[*, 4]"
    },
    "custom_tags": {
        "ResourceClass": "SingleNode",
        "Project": "FGAC-on-ML-Runtime"
    },
    "autotermination_minutes": 60,
    "data_security_mode": "SINGLE_USER",
    "runtime_engine": "STANDARD"
}

print("Creating cluster...")
print(json.dumps(cluster_config, indent=2))

resp = requests.post(
    f"{host}/api/2.0/clusters/create",
    headers=headers,
    json=cluster_config
)

if resp.status_code == 200:
    cluster_id = resp.json()["cluster_id"]
    print(f"\nCluster created successfully!")
    print(f"  Cluster ID: {cluster_id}")
    print(f"  Name: {CLUSTER_NAME}")
    print(f"  Runtime: 16.4 LTS ML (16.4.x-cpu-ml-scala2.12)")
    print(f"  Node: {NODE_TYPE} (single-node)")
    print(f"  Auto-terminate: 60 min")
    print(f"\nCluster is starting... this may take a few minutes.")
else:
    print(f"Error creating cluster: {resp.status_code}")
    print(resp.text)
    cluster_id = None

# COMMAND ----------

# DBTITLE 1,Step 2: Wait for Cluster to Start
if cluster_id:
    print(f"Waiting for cluster {cluster_id} to reach RUNNING state...")
    for i in range(30):
        resp = requests.get(
            f"{host}/api/2.0/clusters/get",
            headers=headers,
            params={"cluster_id": cluster_id}
        )
        state = resp.json().get("state", "UNKNOWN")
        print(f"  [{i*20}s] State: {state}")
        if state == "RUNNING":
            print(f"\nCluster is RUNNING and ready to use!")
            print(f"Cluster ID: {cluster_id}")
            break
        elif state in ["TERMINATED", "ERROR", "TERMINATING"]:
            print(f"\nCluster failed to start: {state}")
            print(resp.json().get("state_message", ""))
            break
        time.sleep(20)
    else:
        print("\nTimed out waiting for cluster to start (10 min).")
        print("Check the Compute page for status.")
else:
    print("No cluster to wait for (creation failed).")

# COMMAND ----------

# DBTITLE 1,Cluster Info Summary
if cluster_id:
    resp = requests.get(
        f"{host}/api/2.0/clusters/get",
        headers=headers,
        params={"cluster_id": cluster_id}
    )
    info = resp.json()
    print("=" * 60)
    print("FGAC ML CLUSTER SUMMARY")
    print("=" * 60)
    print(f"  Name:           {info.get('cluster_name')}")
    print(f"  Cluster ID:     {info.get('cluster_id')}")
    print(f"  State:          {info.get('state')}")
    print(f"  Runtime:        {info.get('spark_version')}")
    print(f"  Node Type:      {info.get('node_type_id')}")
    print(f"  Security Mode:  {info.get('data_security_mode')}")
    print(f"  Auto-terminate: {info.get('autotermination_minutes')} min")
    print("=" * 60)
    print(f"\nAttach your FGAC_Query_Test notebook to this cluster to test.")
