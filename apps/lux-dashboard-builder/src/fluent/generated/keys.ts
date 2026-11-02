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
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|1': {
                        table: 'sys_aix_dashboard_item'
                        id: 'ebb7a383e5330eb0c4cb11c329b5400f'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|2': {
                        table: 'sys_aix_dashboard_item'
                        id: '4df65678004938235cc6ac9a38f66ce9'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|3': {
                        table: 'sys_aix_dashboard_item'
                        id: 'd193a3fc80d0d598c9c28b05dbebd30a'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|4': {
                        table: 'sys_aix_dashboard_item'
                        id: '7e2c6f6129350bd2f33a582a038ebda5'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-widget|5': {
                        table: 'sys_aix_dashboard_item'
                        id: 'a34374a36d204b0de770347f2b30b920'
                    }
                    'aiux-dashboard|x-dash-home-page': {
                        table: 'sys_aix_dashboard'
                        id: 'eb3a671aa5bbfbde3448d571a891dd83'
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
                    }
                    'aiux-page-widget|x-dash-settings-page': {
                        table: 'sys_aix_widget'
                        id: 'c81cda5a047a87d09bce6256def2c0a3'
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
                    'aiux-widget|x-dash-chart-widget': {
                        table: 'sys_aix_widget'
                        id: 'cb054dfc7018cf1b62cdeae26170ff55'
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
                }
                composite: [
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
                        table: 'sys_user_role'
                        id: '726b5ff00db442f9988e1783ebccdba2'
                        key: {
                            name: 'x_steas_dash.builder'
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
                        table: 'sys_documentation'
                        id: 'be09ec0253cb43f5837294cee140654f'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'active'
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
                        table: 'sys_user_role'
                        id: 'd6a7dbccca3e400bbc16a21866f31fbb'
                        key: {
                            name: 'x_steas_dash.admin'
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
                        table: 'sys_documentation'
                        id: 'f4d197edb86d424f9d6828c1d6668a0a'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'secure_count'
                            language: 'en'
                        }
                    },
                ]
            }
        }
    }
}
