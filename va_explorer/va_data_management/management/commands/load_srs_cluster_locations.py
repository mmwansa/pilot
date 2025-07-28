import argparse
import pandas as pd
import numpy as np
from anytree import Node, RenderTree, LevelOrderIter
from django.conf import settings
from django.core.management.base import BaseCommand

from va_explorer.va_data_management.models import SRSClusterLocation


class Command(BaseCommand):
    help = "Loads hierarchical SRS cluster location data from a CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=argparse.FileType("r"))
        parser.add_argument("--delete_previous", type=bool, nargs="?", default=False)

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        delete_previous = options["delete_previous"]

        tree = _treeify_clusters(csv_file)
        _process_cluster_tree(tree, delete_previous)


def _process_cluster_csv(csv_file):
    df = pd.read_csv(csv_file).rename(columns=lambda c: c.lower())
    df = df.fillna("")

    df = df.rename(columns={"status": "is_active"})
    df["is_active"] = df["is_active"].map(lambda x: str(x).strip().lower() == "active")
    return df


def _has_child(parent, label):
    return any(child.name == label for child in parent.children)


def _treeify_clusters(csv_file):
    df = _process_cluster_csv(csv_file)

    root = Node("Zambia", location_type="country")
    node_lookup = {}

    for _, row in df.iterrows():
        prov = row["province"]
        dist = row["district"]
        const = row["constituency"]
        ward = row["ward"]
        ea = row["ea"]
        cluster_code = row["cluster"]
        status = row["is_active"]

        # Province
        p_node = node_lookup.get(prov)
        if not p_node:
            p_node = Node(prov, location_type="province", parent=root)
            node_lookup[prov] = p_node

        # District
        dist_key = f"{prov}-{dist}"
        d_node = node_lookup.get(dist_key)
        if not d_node:
            d_node = Node(dist, location_type="district", parent=p_node)
            node_lookup[dist_key] = d_node

        # Constituency
        const_key = f"{dist_key}-{const}"
        c_node = node_lookup.get(const_key)
        if not c_node:
            c_node = Node(const, location_type="constituency", parent=d_node)
            node_lookup[const_key] = c_node

        # Ward
        ward_key = f"{const_key}-{ward}"
        w_node = node_lookup.get(ward_key)
        if not w_node:
            w_node = Node(ward, location_type="ward", parent=c_node)
            node_lookup[ward_key] = w_node

        # EA (leaf node now)
        ea_key = f"{ward_key}-{ea}"
        if ea_key not in node_lookup:
            ea_node = Node(
                str(ea),
                location_type="ea",
                code=str(cluster_code),      # assign cluster to EA node
                is_active=status,
                parent=w_node,
            )
            node_lookup[ea_key] = ea_node


    if settings.DEBUG:
        for pre, _, node in RenderTree(root):
            print(f"{pre}{node.name}")

    return root


def _get_node_path(node):
    return "{}".format(node.separator.join([""] + [str(n.name) for n in node.path]))


def _process_cluster_tree(tree, delete_previous=False):
    if delete_previous:
        confirm = input("This will delete all SRSClusterLocation data. Continue? (yes/no): ")
        if confirm.lower() not in ["yes", "y"]:
            print("Aborted.")
            return
        SRSClusterLocation.objects.all().delete()

    db_fields = {f.name for f in SRSClusterLocation._meta.get_fields()}
    tree_nodes = list(LevelOrderIter(tree))

    location_ct = update_ct = 0
    db_lookup = {loc.path_string: loc for loc in SRSClusterLocation.objects.all()}

    for node in tree_nodes:
        model_data = {
            k: v for k, v in vars(node).items() if k in db_fields and not k.startswith("_")
        }
        path = _get_node_path(node)

        if node.parent:
            parent_path = _get_node_path(node.parent)
            parent_node = db_lookup.get(parent_path)
            if not parent_node:
                print(f"Missing parent for {node.name}, skipping.")
                continue
            existing = db_lookup.get(path)
            if existing:
                for field, val in model_data.items():
                    setattr(existing, field, val)
                existing.save()
                update_ct += 1
            else:
                new_node = parent_node.add_child(**model_data)
                db_lookup[path] = new_node
                location_ct += 1
        else:
            if path not in db_lookup:
                new_node = SRSClusterLocation.add_root(**model_data)
                db_lookup[path] = new_node
                location_ct += 1

    print(f"  Added: {location_ct}, Updated: {update_ct}")
