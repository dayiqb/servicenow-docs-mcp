import '@servicenow/sdk/global'

declare global {
    namespace Now {
        namespace Internal {
            interface Keys extends KeysRegistry {
                explicit: {
                    'acl-allowed-create': {
                        table: 'sys_security_acl'
                        id: 'f3b7ffc9c49845429e08029f1248b177'
                    }
                    'acl-allowed-delete': {
                        table: 'sys_security_acl'
                        id: '4c02bd74ed8543839746e0dae061b3d1'
                    }
                    'acl-allowed-read': {
                        table: 'sys_security_acl'
                        id: '7649ab5804f94fc4bf55317c7200ca77'
                    }
                    'acl-allowed-write': {
                        table: 'sys_security_acl'
                        id: 'f7a683bf168248ddbcac8d8aeb3fa4ef'
                    }
                    'acl-chart-create': {
                        table: 'sys_security_acl'
                        id: '0c345ffaa49e418db8911e79508d402c'
                    }
                    'acl-chart-delete': {
                        table: 'sys_security_acl'
                        id: '0e520719f4b8482ab0a45c1671f7353e'
                    }
                    'acl-chart-read': {
                        table: 'sys_security_acl'
                        id: '095f1840812a464aacaf1cb0dadb314d'
                    }
                    'acl-chart-write': {
                        table: 'sys_security_acl'
                        id: 'a63d973679984137a6cdd4eb0a39cf29'
                    }
                    'acl-dashboard-create': {
                        table: 'sys_security_acl'
                        id: '931ed9f793ef4ba2b5ebb4f4eb1ae126'
                    }
                    'acl-dashboard-delete': {
                        table: 'sys_security_acl'
                        id: 'a2a7d85a202c41fd9097b4e56b9ea863'
                    }
                    'acl-dashboard-read': {
                        table: 'sys_security_acl'
                        id: 'ea4fc5642bed47fe8c470374517a0d1e'
                    }
                    'acl-dashboard-write': {
                        table: 'sys_security_acl'
                        id: 'd53c4eb2e3664fadb82511056bb57409'
                    }
                    'aiux-acl|x-dash-dashboard-page|read|allow_if|x_steas_dash.viewer': {
                        table: 'sys_security_acl'
                        id: 'f9beb252dc7b4f60be067cf5301a8aa2'
                    }
                    'aiux-acl|x-dash-home-page|read|allow_if|x_steas_dash.viewer': {
                        table: 'sys_security_acl'
                        id: '4feb4a695d9d47b9bd8c0296ea74199a'
                    }
                    'aiux-acl|x-dash-settings-page|read|allow_if|x_steas_dash.admin': {
                        table: 'sys_security_acl'
                        id: 'e47ee9f9de0c44e292cec3b8f2326b6f'
                    }
                    'aiux-color-swatch|lux-dashboard-builder': {
                        table: 'sys_aix_color_swatch'
                        id: 'c1194741db0cb7e88a462cd26b0eb45d'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|0': {
                        table: 'sys_aix_dashboard_item'
                        id: '25e2b0df1238eedd1780f634cd2f7139'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|1': {
                        table: 'sys_aix_dashboard_item'
                        id: 'ebb7a383e5330eb0c4cb11c329b5400f'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|2': {
                        table: 'sys_aix_dashboard_item'
                        id: '4df65678004938235cc6ac9a38f66ce9'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|3': {
                        table: 'sys_aix_dashboard_item'
                        id: 'd193a3fc80d0d598c9c28b05dbebd30a'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|4': {
                        table: 'sys_aix_dashboard_item'
                        id: '7e2c6f6129350bd2f33a582a038ebda5'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|5': {
                        table: 'sys_aix_dashboard_item'
                        id: 'a34374a36d204b0de770347f2b30b920'
                        deleted: true
                    }
                    'aiux-dashboard|x-dash-home-page': {
                        table: 'sys_aix_dashboard'
                        id: 'eb3a671aa5bbfbde3448d571a891dd83'
                        deleted: true
                    }
                    'aiux-dependency|document-title.js': {
                        table: 'sys_aix_dependency'
                        id: 'e50c77973a108f6bedfe737c9488d75e'
                    }
                    'aiux-dependency|gridstack.js': {
                        table: 'sys_aix_dependency'
                        id: 'c90d437dfbd974bfbd7ea0c9ee240a00'
                    }
                    'aiux-experience-page-rel|x-dash-dashboard-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '0067075a99b665a7ccfbdff39861a50c'
                    }
                    'aiux-experience-page-rel|x-dash-home-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: 'b85a2c25170c73e2f4a2cf8fd40b73ba'
                    }
                    'aiux-experience-page-rel|x-dash-settings-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: 'e7278ad9c3bfd72d60b25851d3a8e84b'
                    }
                    'aiux-experience-prop|appHeadCss': {
                        table: 'sys_aix_experience_properties'
                        id: '62d5cedac87c387e36ed3ed3b0b3798d'
                    }
                    'aiux-experience-prop|appTailwindCss': {
                        table: 'sys_aix_experience_properties'
                        id: 'c5f030fe485e0fe1913f8120bb16a58c'
                    }
                    'aiux-experience|lux-dashboard-builder': {
                        table: 'sys_aix_experience'
                        id: '5194a3b9cb68de95978c2546a202c89d'
                    }
                    'aiux-layout-widget|lifecycle': {
                        table: 'sys_aix_widget'
                        id: '8fec46a73d67492f54e96855d350e64f'
                    }
                    'aiux-m2m-experience-dashboard|aiux-experience|lux-dashboard-builder|aiux-dashboard|x-dash-home-page': {
                        table: 'sys_aix_m2m_experience_dashboard'
                        id: '9e7d8f3dc62d5694a2860cab814d07f6'
                        deleted: true
                    }
                    'aiux-m2m-widget-dep|x-dash-board|gridstack.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '52f6e5cafe26d495db05b0b3e511ba53'
                    }
                    'aiux-m2m-widget-dep|x-dash-dashboard-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '48f33ae6ff2b6e873acfb099e9479810'
                    }
                    'aiux-m2m-widget-dep|x-dash-home-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '3dc2873862c99f6b4f1bb777ab0db68e'
                    }
                    'aiux-m2m-widget-dep|x-dash-settings-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: 'b505fdfbbdc56d49d0403eca5fea36bb'
                    }
                    'aiux-page-widget|x-dash-dashboard-page': {
                        table: 'sys_aix_widget'
                        id: '34fd217bebe2053609bb073aa614c7e5'
                    }
                    'aiux-page-widget|x-dash-home-page': {
                        table: 'sys_aix_widget'
                        id: '62aace435216d9f5ad5cc6c270bf46f0'
                    }
                    'aiux-page-widget|x-dash-settings-page': {
                        table: 'sys_aix_widget'
                        id: 'c81cda5a047a87d09bce6256def2c0a3'
                    }
                    'aiux-page|x-dash-dashboard-page': {
                        table: 'sys_aix_page'
                        id: 'a19ff7d724cc0138b4b3dbe8638094a8'
                    }
                    'aiux-page|x-dash-home-page': {
                        table: 'sys_aix_page'
                        id: '55ccfba069eea3f6eba8c5c82b408a5f'
                    }
                    'aiux-page|x-dash-settings-page': {
                        table: 'sys_aix_page'
                        id: '73c9a4f6784ad88e5ee4eeb0b52d493b'
                    }
                    'aiux-project|x_steas_dash': {
                        table: 'sys_aix_project'
                        id: '3afc4a928b989a357c8f0a35607dfbf1'
                    }
                    'aiux-theme|lux-dashboard-builder': {
                        table: 'sys_aix_theme'
                        id: 'bed9f1cb017b12e44ad37b1a57250f81'
                    }
                    'aiux-widget|x-dash-board': {
                        table: 'sys_aix_widget'
                        id: '556b1176c57c4a710ee78ef7bc1165d7'
                    }
                    'aiux-widget|x-dash-chart-widget': {
                        table: 'sys_aix_widget'
                        id: 'cb054dfc7018cf1b62cdeae26170ff55'
                        deleted: true
                    }
                    'aiux-widget|x-dash-dashboards': {
                        table: 'sys_aix_widget'
                        id: 'a92c6700322c46b010448b24568f0238'
                    }
                    'aiux-widget|x-dash-settings': {
                        table: 'sys_aix_widget'
                        id: 'abecdb17fab951b75d157a890cca975c'
                    }
                    'allowed-incident': {
                        table: 'x_steas_dash_allowed_table'
                        id: '3fc3f58501ec4eaf91b68f5dd1069212'
                    }
                    'allowed-task': {
                        table: 'x_steas_dash_allowed_table'
                        id: '65660bf05d5d40fab767034e08805e7c'
                    }
                    bom_json: {
                        table: 'sys_module'
                        id: '9d642409c53d48879cd442f49db40de7'
                    }
                    package_json: {
                        table: 'sys_module'
                        id: 'ae056dc26130420f806bd699a7ae74eb'
                    }
                    'sample-chart-category': {
                        table: 'x_steas_dash_chart'
                        id: 'b4e65d8a941440cc9093e4cb324b92eb'
                    }
                    'sample-chart-heat': {
                        table: 'x_steas_dash_chart'
                        id: '42e4297e539e4629b2f39ae78399176f'
                    }
                    'sample-chart-open': {
                        table: 'x_steas_dash_chart'
                        id: '6b466a402c57402c84d9493f8dff96a0'
                    }
                    'sample-chart-priority': {
                        table: 'x_steas_dash_chart'
                        id: '3aa93b0fa21c4d339a6049eb12098e88'
                    }
                    'sample-chart-state': {
                        table: 'x_steas_dash_chart'
                        id: 'f807e177f5bc43b682920dc5f4390396'
                    }
                    'sample-dashboard': {
                        table: 'x_steas_dash_dashboard'
                        id: '158193c165804b259f6eb3dbc7391088'
                    }
                }
                composite: [
                    {
                        table: 'sys_choice'
                        id: '016eb0b1457b4ae89f4f96cb0d8d615b'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'none'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '038d18f612714b999566b442b3ebcf76'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'max_groups'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '0ce98a7a72bc4b8f81e61c00ccdf41de'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_y'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '0ec05992060a436da5d8ee1224161e34'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'donut'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '0f6b02489ca94c7faa37ffab06ec2eb9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'title'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0fd427c3a7724af99f307a534888cd80'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate_field'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '11bee15d56e4488d82650003c4b56a53'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'score'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '1392a3fbc3394bcfaf388f056c6340dd'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '13e35638e7364cd58909061c22210ce8'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '1e3f1f76007b4db3a6a76c29e95dbd9e'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '1e68306aeffd4456bd6e58d16f5deeeb'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '2113794bc457480a9044386228dbc38a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'area'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '2679e70d36d245fb8071752b06ed5112'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'query'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '26e67619bcbe4e988987ca3fe0417495'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'heatmap'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '2b70352cf9b44dec85e938af162ae95a'
                        key: {
                            sys_security_acl: 'a2a7d85a202c41fd9097b4e56b9ea863'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '2df8bb3349b645aaa46b367524970d86'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '2e2f15eefbe348a7ae9dc3b7073c4dfd'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_h'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '30455e144d7b43c09456bbb33c9bd693'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_index'
                        id: '30caaebac1894e9eb24bb1ed7506269f'
                        key: {
                            logical_table_name: 'x_steas_dash_allowed_table'
                            col_name_string: 'source_table'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '314adf959db248b68d708e0d3b078db1'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '330e492936684d579641bde0e883f9bf'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '3313e9814dbc49f3b23c5d04ef2e1618'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'pie'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '350a70d1ce80407d91e2b7b7ca0532ee'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '3617f1b7888e475eb6cd4f2c05b4c5a7'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact_m2m'
                        id: '36c51869578c4c13945ea44827cf1bc9'
                        key: {
                            application_file: '3afc4a928b989a357c8f0a35607dfbf1'
                            source_artifact: 'd4c1fe6d0b3442b3b1e6d37c3d082e7c'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '3afafdaf215e40e6959d14bfba702924'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '3cfce0e7c50e489f840d3506b3be2cc9'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'description'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '3d580783b00f43ab811b8f76455f8a1e'
                        key: {
                            sys_security_acl: 'a63d973679984137a6cdd4eb0a39cf29'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '3f4839b125184a16960ad1ff499c5f9a'
                        key: {
                            name: 'x_steas_dash_chart'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '4000e387ce82407e977487f4521b8c5b'
                        key: {
                            sys_security_acl: 'f7a683bf168248ddbcac8d8aeb3fa4ef'
                            sys_user_role: {
                                id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '40ff9f5a20fc418eaf48023051e47aed'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'shared'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '417dc66eeba745adb598ffff07843dfb'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '41a24fba1d1247fca3b62457cd959d75'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '41ce3e100f8f455595c7e775ac743d22'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'secure_count'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '425e4abc67844d2d9fd937e0d0e3ab6f'
                        key: {
                            name: 'x_steas_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '43551bae1c564b3b868d5878c96a464f'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Year'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '437b01233170480b8d1ae586648de3bb'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '47409349b15640538fee7d89b3c05ee0'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by_2'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '4aaa128004bd4abd87651b1808a3a973'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '4bc171efb80e4cdfa6d5e801be4bc72b'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'description'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '506536dcf72740e0b8efbeefdda77c53'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '524cc187b4064931a042ece046d89d4d'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by_2'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '53db0ffda5404c129dde2cfc48785335'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '595157a548c74c65bfbe4bef589d54cb'
                        key: {
                            sys_security_acl: 'ea4fc5642bed47fe8c470374517a0d1e'
                            sys_user_role: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '5a6c23a101b04bcda78c33100ad8d73c'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'shared'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '5ffd3b86f26447afb7d40871a7e40b95'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'line'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '60e2108750b8422bb4c76a6bacd0479f'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'MAX'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '64cebd3fbac14df587257efa19b502c6'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_x'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: '662cdd514180446aa98d51a8b424119b'
                        key: {
                            role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                            contains: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '665baa65c4d0464fadfe2feaa930c3b7'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'stacked'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '6b51df337bf0400a99988d5fcfe8db78'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'dashboard'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '6b523ad2568f464f84d846e48c4f94da'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'owner'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '6b645d6223d44648a5efaa856355f2ea'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'list'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '6ce05c5ac7f24294a822941deb5ca300'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '72106b53673e44d2b4e9fd59be4c854c'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'max_groups'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: '726b5ff00db442f9988e1783ebccdba2'
                        key: {
                            name: 'x_steas_dash.builder'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '72fd8f43ee9b407b92dd78a6129af946'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'MIN'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: '73ba117416cb4311abb8c1e1b84358da'
                        key: {
                            name: 'x_steas_dash.viewer'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '767bac25310b42c096ddc6aa6dc33f97'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Week'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '770c246bd53a44b383e0390d63b74abd'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'name'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '7b1fd6a3a4cd4bdabd1ed8dc4bebd8e1'
                        key: {
                            sys_security_acl: '095f1840812a464aacaf1cb0dadb314d'
                            sys_user_role: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '7d5a8ecc12b24560a7ee8ed752c20c0a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '7d9c2b4976124ababfdf9a8a6da7764e'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '7f0281ae98ec4c62800293cfa6bd5673'
                        key: {
                            sys_security_acl: '931ed9f793ef4ba2b5ebb4f4eb1ae126'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '80d70ff173d14c4c8f3c22cdfca1cee6'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'list_fields'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '8150ef6bf23f4528b46622bee5fe3edf'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'title'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '84666e40739746139c12bdf86e64e075'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'bar'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '84b4c2dee31a40b6a5627ea2193f66f2'
                        key: {
                            name: 'x_steas_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '8b2d1d45f8d348f2a6e0afce98897ff8'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Day'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '8e3d0f8d948945e6810ed8c41b0d0376'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '8e4bb9da069647d8aae74853e193c10b'
                        key: {
                            sys_security_acl: 'e47ee9f9de0c44e292cec3b8f2326b6f'
                            sys_user_role: {
                                id: '1bd74e3117b0400b8b5d8a877fbeb4a0'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '8f3fe5f96f244ceba9b8cf057551dc9a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Month'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '94fad09efa87418494d5d263b85b09b1'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'COUNT'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '95d02034fca447da8006a6f3279868d8'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '992bb134dde54f5a98988a01a0fc7b16'
                        key: {
                            name: 'x_steas_dash_chart'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '9a0c697426374be7bcf4eb2f07fd7f94'
                        key: {
                            sys_security_acl: '4c02bd74ed8543839746e0dae061b3d1'
                            sys_user_role: {
                                id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'a300476834e3481ba0089e9afaf198c3'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_w'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: 'a5e3e527d0d3417cb73552f1e477e196'
                        key: {
                            role: {
                                id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                            contains: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'a7cde36ee90348f8b9ccda4533bf4b60'
                        key: {
                            sys_security_acl: '4feb4a695d9d47b9bd8c0296ea74199a'
                            sys_user_role: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'ae537b55e0944e5a967a76048f325031'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'column'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'ae9817526377447eb181075bbaefb28c'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_w'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'af61c4218ba440ee8be79a8c8af5ad54'
                        key: {
                            sys_security_acl: '7649ab5804f94fc4bf55317c7200ca77'
                            sys_user_role: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'b2e313fe51aa4d56952d06347fa00e61'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'list_fields'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'b7345c5aefb34c14a3e88ba9e74c9d1f'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_y'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'b7466f798bb949c5bfb978a263288774'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_h'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'b8a1f9e3ce344962a0fc8f254fb7ca3a'
                        key: {
                            sys_security_acl: 'f3b7ffc9c49845429e08029f1248b177'
                            sys_user_role: {
                                id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'bd1fc31d4c474316b6ac63922e5c8838'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Quarter'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'be09ec0253cb43f5837294cee140654f'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c1a36102d005405f89cc55731e341956'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'name'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c3a23f575d6c4dd8953bdc51c6e4a3b9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c781dbb528174a56a721e867c27bd145'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'query'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'd3c42f4b48824248adb54ad70b892d78'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact'
                        id: 'd4c1fe6d0b3442b3b1e6d37c3d082e7c'
                        key: {
                            name: 'aiux-source 3afc4a928b989a357c8f0a35607dfbf1'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'd63a337c598849aab790e34a9cf610d7'
                        key: {
                            sys_security_acl: 'd53c4eb2e3664fadb82511056bb57409'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'd6a0631529494e9bb16e411ee03b1af5'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                        key: {
                            name: 'x_steas_dash.admin'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'e17cdf3a60c249c29672b0f90c2a7888'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'AVG'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'e9f4269cacd944d2bf9144fc559c6e04'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_x'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'ec5542de933b49da893c559f76f7931d'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'ecf21dd4373741acaed5948e15c900f7'
                        key: {
                            sys_security_acl: '0e520719f4b8482ab0a45c1671f7353e'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'ed81f7574ce140cda408daa92d7c42d9'
                        key: {
                            sys_security_acl: '0c345ffaa49e418db8911e79508d402c'
                            sys_user_role: {
                                id: '726b5ff00db442f9988e1783ebccdba2'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f467eb25f01b406fb02a2ef692b73fe5'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'dashboard'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f4d197edb86d424f9d6828c1d6668a0a'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'secure_count'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'f955f8c3f87b40d8a266fb9ba0e52418'
                        key: {
                            sys_security_acl: 'f9beb252dc7b4f60be067cf5301a8aa2'
                            sys_user_role: {
                                id: '73ba117416cb4311abb8c1e1b84358da'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'fa82c06fc1474e2aa83a4649f2ad6b28'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate_field'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'fa999828a59c42899db9a0fc68a2a940'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'owner'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'fad7201298fb448184fc03d76058c983'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'SUM'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                ]
            }
        }
    }
}
