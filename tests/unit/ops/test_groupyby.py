#
# Copyright (c) 2021, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import dask.dataframe as dd
import numpy as np
import pandas as pd
import pytest

import nvtabular as nvt
from merlin.core.dispatch import make_df
from nvtabular import ColumnSelector, Schema, Workflow, ops

try:
    import cudf

    _CPU = [True, False]
except ImportError:
    _CPU = [True]


@pytest.mark.parametrize("cpu", _CPU)
@pytest.mark.parametrize("ascending", [True, False])
@pytest.mark.parametrize("keys", [["name"], "id", ["name", "id"]])
def test_groupby_op(keys, cpu, ascending):
    # Initial timeseries dataset
    size = 60
    df1 = make_df(
        {
            "name": np.random.choice(["Dave", "Zelda"], size=size),
            "id": np.random.choice([0, 1], size=size),
            "ts": np.linspace(0.0, 10.0, num=size),
            "x": np.arange(size),
            "y": np.linspace(0.0, 10.0, num=size),
            "shuffle": np.random.uniform(low=0.0, high=10.0, size=size),
        }
    )
    df1 = df1.sort_values("shuffle").drop(columns="shuffle").reset_index(drop=True)

    # Create a ddf, and be sure to shuffle by the groupby keys
    ddf1 = dd.from_pandas(df1, npartitions=3).shuffle(keys)
    dataset = nvt.Dataset(ddf1, cpu=cpu)

    dataset.schema.column_schemas["x"] = dataset.schema.column_schemas["x"].with_tags("custom_tag")
    # Define Groupby Workflow
    groupby_features = ColumnSelector(["name", "id", "ts", "x", "y"]) >> ops.Groupby(
        groupby_cols=keys,
        sort_cols=["ts"],
        aggs={
            "x": ["list", "sum", "first", "last"],
            "y": ["first", "last"],
            "ts": ["min"],
        },
        name_sep="-",
        ascending=ascending,
    )
    processor = nvt.Workflow(groupby_features)
    processor.fit(dataset)
    new_gdf = processor.transform(dataset).to_ddf().compute()

    assert "custom_tag" in processor.output_schema.column_schemas["x-list"].tags

    if not cpu:
        # Make sure we are capturing the list type in `output_dtypes`
        assert (
            processor.output_schema["x-list"].dtype
            == cudf.core.dtypes.ListDtype("int64").element_type
        )
        assert processor.output_schema["x-list"].is_list is True
        assert processor.output_schema["x-list"].is_ragged is True

    # Check list-aggregation ordering
    x = new_gdf["x-list"]
    x = x.to_pandas() if hasattr(x, "to_pandas") else x
    sums = []
    for el in x.values:
        _el = pd.Series(el)
        sums.append(_el.sum())
        if ascending:
            assert _el.is_monotonic_increasing
        else:
            assert _el.is_monotonic_decreasing
    # Check that list sums match sum aggregation
    x = new_gdf["x-sum"]
    x = x.to_pandas() if hasattr(x, "to_pandas") else x
    assert list(x) == sums

    # Check basic behavior or "y" column
    assert (new_gdf["y-first"] < new_gdf["y-last"]).all()

    for i in range(len(new_gdf)):
        if ascending:
            assert new_gdf["x-first"].iloc[i] == new_gdf["x-list"].iloc[i][0]
        else:
            assert new_gdf["x-first"].iloc[i] == new_gdf["x-list"].iloc[i][-1]


@pytest.mark.parametrize("cpu", _CPU)
def test_groupby_string_agg(cpu):
    # Initial sales dataset
    size = 60
    df1 = make_df(
        {
            "product_id": np.random.randint(10, size=size),
            "day": np.random.randint(7, size=size),
            "price": np.random.rand(size),
        }
    )
    ddf1 = dd.from_pandas(df1, npartitions=3).shuffle(["day"])
    dataset = nvt.Dataset(ddf1, cpu=cpu)

    groupby_features = ColumnSelector(["product_id", "day", "price"]) >> ops.Groupby(
        groupby_cols=["day"], aggs="count"
    )

    processor = nvt.Workflow(groupby_features)
    processor.fit(dataset)
    processor.transform(dataset).to_ddf().compute()


def test_groupby_selector_cols():
    input_schema = Schema(["name", "id", "ts", "x", "y"])

    # Include the groupby col in the selector
    groupby = ColumnSelector(["name", "id", "ts", "x", "y"]) >> ops.Groupby(
        groupby_cols=["name"],
        sort_cols=["ts"],
        aggs={
            "x": ["list", "sum"],
            "y": ["first", "last"],
            "ts": ["min"],
        },
        name_sep="-",
    )
    workflow = Workflow(groupby).fit_schema(input_schema)

    # If groupby_cols are included in the selector, they should be in the output
    assert "name" in workflow.output_node.output_schema.column_names

    # Don't include the groupby col in the selector
    groupby = ColumnSelector(["id", "ts", "x", "y"]) >> ops.Groupby(
        groupby_cols=["name"],
        sort_cols=["ts"],
        aggs={
            "x": ["list", "sum"],
            "y": ["first", "last"],
            "ts": ["min"],
        },
        name_sep="-",
    )
    workflow = Workflow(groupby).fit_schema(input_schema)

    # If groupby_cols aren't included in the selector, they shouldn't be in the output
    assert "name" not in workflow.output_node.output_schema.column_names


@pytest.mark.parametrize("cpu", _CPU)
def test_groupby_without_selector_in_groupby_cols(cpu):
    # Initial sales dataset
    size = 60
    df1 = make_df(
        {
            "product_id": np.random.randint(10, size=size),
            "day": np.random.randint(7, size=size),
            "price": np.random.rand(size),
        }
    )
    ddf1 = dd.from_pandas(df1, npartitions=3).shuffle(["day"])
    dataset = nvt.Dataset(ddf1, cpu=cpu)

    groupby_features = ["product_id"] >> ops.Groupby(groupby_cols=["day"], aggs="count")

    processor = nvt.Workflow(groupby_features)
    processor.fit(dataset)
    assert processor.transform(dataset).to_ddf().compute().columns.tolist() == ["product_id_count"]


@pytest.mark.parametrize("cpu", _CPU)
def test_groupby_casting_in_aggregations(cpu):
    # Initial dataset
    size = 60
    names = ["Dave", "Zelda"]
    df1 = make_df(
        {
            "name": np.random.choice(names, size=size),
            "x": np.random.randint(0, 2, size=size).astype(np.int8),
            "y": np.linspace(0.0, 10.0, num=size),
            "z": np.linspace(0.0, 10.0, num=size).astype(np.float32),
            "shuffle": np.random.uniform(low=0.0, high=10.0, size=size),
        }
    )
    df1 = df1.sort_values("shuffle").drop(columns="shuffle").reset_index(drop=True)

    # Create a ddf, and be sure to shuffle by the groupby keys
    ddf1 = dd.from_pandas(df1, npartitions=3).shuffle("name")
    dataset = nvt.Dataset(ddf1, cpu=cpu)

    # Define Groupby Workflow
    aggs_to_test = ["mean", "std", "var", "median", "nunique", "sum"]
    groupby_features = ColumnSelector(["name", "x", "y", "z"]) >> ops.Groupby(
        groupby_cols="name",
        aggs={"x": aggs_to_test, "y": aggs_to_test, "z": aggs_to_test},
        name_sep="-",
    )
    processor = nvt.Workflow(groupby_features)
    processor.fit(dataset)
    new_gdf = processor.transform(dataset).to_ddf().compute()

    df1.set_index("name", inplace=True)
    for agg in aggs_to_test:
        for col in list("xyz"):
            for name in names:
                without_agg = getattr(df1.loc[name][col], agg)()
                with_agg = new_gdf.loc[new_gdf.name == name, f"{col}-{agg}"]
                with_agg = with_agg.item() if hasattr(with_agg, "item") else with_agg.loc[0][0]
                assert np.allclose(without_agg, with_agg)


@pytest.mark.parametrize("cpu", _CPU)
def test_groupby_column_names_containing_aggregations(cpu):
    # Initial dataset
    size = 60
    names = ["Dave", "Zelda"]
    # The column to be aggregated contains name of an aggregation -- count.
    # This could lead to it being cast to incorrect dtype.
    df1 = make_df(
        {
            "name": np.random.choice(names, size=size),
            "test_score_counting_to_10": np.random.uniform(low=0.0, high=10.0, size=size),
        }
    )

    # Create a ddf, and be sure to shuffle by the groupby keys
    ddf1 = dd.from_pandas(df1, npartitions=3).shuffle("name")
    dataset = nvt.Dataset(ddf1, cpu=cpu)

    # Define Groupby Workflow
    groupby_features = ["name", "test_score_counting_to_10"] >> ops.Groupby(
        groupby_cols="name", aggs={"test_score_counting_to_10": "mean"}
    )
    processor = nvt.Workflow(groupby_features)
    processor.fit(dataset)
    new_gdf = processor.transform(dataset).to_ddf().compute()

    assert new_gdf is not None


@pytest.mark.parametrize("cpu", _CPU)
def test_groupby_list_first_last(cpu):
    # Initial dataset
    df = make_df(
        {
            "user_id": [1, 1, 2, 3],
            "user_vector": [[1, 2, 3], [4, 5, 6], [2, 2, 3], [3, 2, 3]],
        }
    )
    ddf = dd.from_pandas(df, npartitions=3)
    dataset = nvt.Dataset(ddf, cpu=cpu)

    # Define Groupby Workflow
    output = df.columns >> ops.Groupby(
        groupby_cols="user_id",
        aggs={"user_vector": ["first", "last"]},
    )
    workflow = nvt.Workflow(output)
    out = workflow.fit_transform(dataset).compute()

    def _flatten_ser(ser):
        if cpu:
            # Nested list may be a np.ndarray
            return [r.tolist() if hasattr(r, "tolist") else r for r in ser]
        return ser.to_arrow().tolist()

    # Check "first" and "last" aggregations
    assert _flatten_ser(out["user_vector_first"]) == [[1, 2, 3], [2, 2, 3], [3, 2, 3]]
    assert _flatten_ser(out["user_vector_last"]) == [[4, 5, 6], [2, 2, 3], [3, 2, 3]]
