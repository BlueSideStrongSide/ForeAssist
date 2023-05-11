import json
import re

import yaml
import streamlit as st
import argparse
import pandas as pd
from pathlib import Path


REFERENCES = ["https://www.jaiminton.com/cheatsheet/DFIR/",
              "https://github.com/ForensicArtifacts/artifacts"
              ]

#streamlit global config
st.set_page_config(layout="wide")

def main():
    build_streamlit_app()
    return 1

@st.cache_data
def read_supported_artifacts(wanted_os:list=None):
    artifact_source = Path("share/artifacts")

    # pass all files in that match the supplied patter
    artifact_list = artifact_source.glob('**/*.yaml')

    #get a count of artifacts by OS to use later
    stats_by_os = {}
    for os in wanted_os:
        stats_by_os[os] = 0


    parsed_artifacts = []
    for artifact in artifact_list:

        with open(str(artifact), mode="rb") as artifact_bin:
            read_backend_artifacts = yaml.safe_load_all(artifact_bin)

            for item in read_backend_artifacts:
                for os in wanted_os:
                    if not os == "Any":
                        item_filter = item.get("supported_os")
                        if item_filter and (os in item_filter):
                            parsed_artifacts.append(item)
                            stats_by_os[os] +=1
                    else:
                        stats_by_os[os] += 1
                        parsed_artifacts.append(item)

    return parsed_artifacts, stats_by_os

@st.cache_data
def read_selected_os_checkbox(checkbox_options) -> dict[str,bool]:
    wanted_os = []
    for option, enabled in checkbox_options.items():
        if enabled:
            wanted_os.append(option)

    return wanted_os

@st._cache_data
def render_selected_artifacts(imported_artifacts=None, selected_artifact=None):

    #return the filtered object keep all writes in streamlit function
    for st_ready_artifact in imported_artifacts:
        if st_ready_artifact["name"] == selected_artifact:
            return st_ready_artifact

def filter_view_all_dataframe(current_dataframe:pd.DataFrame=None, _modification_container=None, _filter_checkbox=None):

    with _modification_container:

        if _filter_checkbox:
            to_filter_col = st.multiselect("Filter Artifacts Data On:", ("name","doc","Sources", "supported_os"), default=("name"))
            if to_filter_col:
                for item in to_filter_col:
                    padding_left, padding_right = st.columns((1, 100))
                    input_left, input_right = st.columns((1, 100))
                    wanted_substring = padding_right.text_input(f"↳ Substring found in -->  {item}:")
                    if wanted_substring and item == "supported_os":
                        current_dataframe = current_dataframe[current_dataframe["supported_os"].apply(lambda x:  len(x)==1 and x[0] == wanted_substring)]
                    elif wanted_substring:
                        current_dataframe = current_dataframe[current_dataframe[item].str.contains(wanted_substring, case=False)]


    return current_dataframe

def render_all_selected_artifacts(imported_artifacts:list=None, _modification_container=None, _filter_checkbox=None) -> pd.DataFrame:
    base_df = pd.DataFrame(imported_artifacts)

    #search through col and keep the highest value for the length
    max_cols = max([len(s) for s in base_df['sources']])

    #normalize json for nested data
    sources_normalized = pd.json_normalize(base_df['sources'])

    #reindex cols to the maximum number of cols
    sources_normalized = sources_normalized.reindex(range(max_cols), axis=1)

    # rename the resulting cols
    temp_names = [f'Source_{i+1}' for i in range(max_cols)]
    sources_normalized.columns = temp_names


    # use lambda to concat values from all cols into one col, also drop empty and set type
    sources_concatenated = sources_normalized.apply(lambda x: '\n\n'.join(x.dropna().astype(str)), axis=1)

    #concats our new col into a new datframe
    result_df = pd.concat([base_df[["name", "doc", "supported_os", "urls" ]], sources_concatenated],axis=1)

    result_df = result_df.rename(columns={0:'Sources'})

    #call filter function return dataframe to outter function
    filtered_df = filter_view_all_dataframe(current_dataframe=result_df,
                                            _modification_container=_modification_container,
                                            _filter_checkbox=_filter_checkbox)
    return filtered_df

@st._cache_data
def export_rendered_artifacts_by_type(input_data_frame:pd.DataFrame=None,_export_options:dict=None,selected_export_type:str=None):
    extended_options=None
    for type, export_method in _export_options.items():
        if selected_export_type == type:
            return export_method(input_data_frame)

#update streamlit
@st._cache_data
def build_env_var_expansion(input_data_frame:pd.DataFrame) -> list:
    identified_filters = []
    #%%environ_allusersprofile%% use regext to parse this patter return hits to set for uniq
    temp_df = pd.DataFrame()
    temp_df = input_data_frame["Sources"].str.extract('(%%[^,\\\]+%%)').dropna()

    if not temp_df.empty:
        identified_filters = set(temp_df[0].to_list())

    return identified_filters

@st._cache_data
def selected_artifact_stats(selected_artifacts, st_provided_stats):
    #knock out logic to count items by OS
    # what happens when an artiifact shows in both
    # that artifact should be counted twice


    artifact_stats = ({"Total Artifacts":len(selected_artifacts),
                      "Total Artifacts By OS":st_provided_stats})

    return pd.DataFrame.from_dict([artifact_stats]).astype(str).transpose()

def build_streamlit_app() ->None:
    rendered_dataframe = None

    #Build This Dynamically
    supported_os = ("Any", "Windows", "Linux", "Darwin", "ESXi")

    supported_exports = {"csv":pd.DataFrame.to_csv,
            "json": pd.DataFrame.to_json,
            "md":pd.DataFrame.to_markdown}

    supported_export_types = supported_exports.keys()

    st.title("ForeAssist")
    st.write(f'"An OpenSource project pulling together forensic artifacts from a few community projects. ')
    st.write(f'The goal is to have an easy and friendly way to find relevant artifacts and supporting information on each. ')
    st.write(f'Currently this page uses the awesome! work of the resources listed.')
    st.write(f'Credit and attribution will be associated with any adhoc additions as well!')
    st.markdown("""
    - https://www.jaiminton.com/cheatsheet/DFIR/
    - https://github.com/ForensicArtifacts/artifacts
    """)

    st.sidebar.file_uploader(
        "Give me a list of available filenames, I will check if any match a LIKELY forensic artifact")

    st.write("What OS are you interested in?")

    checkbox_options = {}
    for item,os in enumerate(supported_os):
            selected_os = st.checkbox(os, key=item)
            checkbox_options[os] = selected_os
    st_ready_artifacts, st_ready_stats = read_supported_artifacts(wanted_os=read_selected_os_checkbox(checkbox_options))

    selected_artifact_visbility = "hidden"
    st.sidebar.subheader("Collection Scripts:")
    st.sidebar.button("Collect Windows Selected Artifacts")
    st.sidebar.button("Collect Linux Selected Artifiacts")
    st.sidebar.button("Collect Artifacts Using Python")

    if any([x for x in checkbox_options.values()]):
        st.subheader("Included Artifacts")
        # artifact stats

        hide_table_row_index = """
                    <style>
                    thead tr:first-child {display:none}
                    </style>
                    """
        st.markdown(hide_table_row_index, unsafe_allow_html=True)

        st.table(selected_artifact_stats(st_ready_artifacts, st_ready_stats))

        st.subheader("Filters")
        view1, view2, = st.columns(2)
        with view1:
            check_view_all = st.checkbox("View All Artifacts")

        if check_view_all:
            with view2:
                check_additional_filters = st.checkbox("Apply Additional Filters")

            data_modification_container = st.container()

            st.subheader("Results:")

            rendered_dataframe = render_all_selected_artifacts(imported_artifacts=st_ready_artifacts,
                                          _modification_container=data_modification_container,
                                          _filter_checkbox=check_additional_filters)

            if not rendered_dataframe.empty:
                wanted_expansion = build_env_var_expansion(input_data_frame=rendered_dataframe)
                if wanted_expansion:
                    st.sidebar.subheader("Environment Variables")
                    st.sidebar.write("Use the section below to expand provided environment variables.")
                    for item in wanted_expansion:
                        st.sidebar.text_input(item, "")


                st.sidebar.subheader("Export:")
                export_type = st.sidebar.selectbox(label="Type:", options=supported_export_types)

                btn_export_clicked = st.sidebar.download_button(label="Export Filtered Artifacts",
                                                                file_name=f"filtered_exports.{export_type}",
                                                                data=export_rendered_artifacts_by_type(
                                                                    input_data_frame=rendered_dataframe,
                                                                    _export_options=supported_exports,
                                                                    selected_export_type=export_type))
            st.dataframe(rendered_dataframe)

        else:
            selected_artifact_visbility = "visible"

            #build select box of artifacts macthing the OS filter
            selected_artifact = st.selectbox("Included Artifacts", [st_ready_label['name'] for st_ready_label in st_ready_artifacts],
                                             label_visibility=selected_artifact_visbility)

            #We may need to update and pass a placeholder here
            rendered_dataframe = render_selected_artifacts(imported_artifacts=st_ready_artifacts, selected_artifact=selected_artifact)

            st.subheader("Results:")
            st.json(rendered_dataframe, expanded=True)

    st.write(f'Certain functionaility is still being added, please see the github repo for current issues/enhancements/bugs.'
             f' https://github.com/BlueSideStrongSide/ForeAssist/issues.')


if __name__ == '__main__':
    main()
