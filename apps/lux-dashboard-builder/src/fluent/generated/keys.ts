import '@servicenow/sdk/global'

declare global {
    namespace Now {
        namespace Internal {
            interface Keys extends KeysRegistry {
                explicit: {
                    'acl-allowed-create': {
                        table: 'sys_security_acl'
                        id: '9d457858f88c47c4a8e41b09fff9918a'
                    }
                    'acl-allowed-delete': {
                        table: 'sys_security_acl'
                        id: 'ac392cfdb27e4df4937c22d6b56edc20'
                    }
                    'acl-allowed-read': {
                        table: 'sys_security_acl'
                        id: 'af95ca266f0c4284bbe46526356851a7'
                    }
                    'acl-allowed-write': {
                        table: 'sys_security_acl'
                        id: 'eedfa4d6be514f0a9df3becc128bbdf0'
                    }
                    'acl-chart-create': {
                        table: 'sys_security_acl'
                        id: 'bb7694804d9c4bce88de9a32d8242554'
                    }
                    'acl-chart-delete': {
                        table: 'sys_security_acl'
                        id: 'cef3882bcf7d4a869b2baa12308090dc'
                    }
                    'acl-chart-read': {
                        table: 'sys_security_acl'
                        id: '5932a844addb44f6a0bdf61e21b9b8e1'
                    }
                    'acl-chart-write': {
                        table: 'sys_security_acl'
                        id: 'bf14b1498c4c4072b5cf1fc6f78bf64c'
                    }
                    'acl-dashboard-create': {
                        table: 'sys_security_acl'
                        id: '319d2f11a0f74c19b6d8f161059f9bba'
                    }
                    'acl-dashboard-delete': {
                        table: 'sys_security_acl'
                        id: 'aacc2de2954d45a0b49f00b71907e4fe'
                    }
                    'acl-dashboard-read': {
                        table: 'sys_security_acl'
                        id: '4c0b81598a3f485cab324d7b09f01d5a'
                    }
                    'acl-dashboard-write': {
                        table: 'sys_security_acl'
                        id: '6adf7eae6bef46a68e25b3d7672eeaa5'
                    }
                    'aiux-acl|x-dash-dashboard-page|read|allow_if|x_steas_dash.viewer': {
                        table: 'sys_security_acl'
                        id: '790d4d824b9449118e63f7102708c877'
                    }
                    'aiux-acl|x-dash-dashboards-page|read|allow_if|x_steas_dash.viewer': {
                        table: 'sys_security_acl'
                        id: '6c9b25932b0849448f972a6c776da7af'
                    }
                    'aiux-acl|x-dash-home-page|read|allow_if|x_steas_dash.viewer': {
                        table: 'sys_security_acl'
                        id: 'a7f8ea7bea9a4c53ad30d571453b7fc1'
                        deleted: false
                    }
                    'aiux-acl|x-dash-settings-page|read|allow_if|x_steas_dash.admin': {
                        table: 'sys_security_acl'
                        id: '8096bad983644bc18610d9ea8cd11a8e'
                    }
                    'aiux-color-swatch|lux-dashboard-builder': {
                        table: 'sys_aix_color_swatch'
                        id: 'c1194741db0cb7e88a462cd26b0eb45d'
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|0': {
                        table: 'sys_aix_dashboard_item'
                        id: '85bb4579a38b5994e822135bd5276965'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|1': {
                        table: 'sys_aix_dashboard_item'
                        id: 'b2ba3e962306be753705041c5484ac78'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|2': {
                        table: 'sys_aix_dashboard_item'
                        id: '0661b826ec1670faa72171f5e7c616d4'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|3': {
                        table: 'sys_aix_dashboard_item'
                        id: '1c5dcd874d5fe11075b9bd287a0b7f65'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|4': {
                        table: 'sys_aix_dashboard_item'
                        id: '66e6ff43cf17dc50b5dc41bf1c87ac68'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|5': {
                        table: 'sys_aix_dashboard_item'
                        id: '06c59169c1000baa7f66e97e85fd45ae'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|6': {
                        table: 'sys_aix_dashboard_item'
                        id: '277ae1481680fa807731d916d551f60e'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|7': {
                        table: 'sys_aix_dashboard_item'
                        id: '8cc1739178044c25d2eb1fed72614690'
                        deleted: true
                    }
                    'aiux-dashboard-item|x-dash-home-page|x-dash-chart-tile|8': {
                        table: 'sys_aix_dashboard_item'
                        id: '690ba15c89bc22c5da4255be3c2fdfd2'
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
                    'aiux-dependency|x-dash-chart.js': {
                        table: 'sys_aix_dependency'
                        id: 'c6fe2c5ece14fa8c66eb9d014b78d7c0'
                    }
                    'aiux-experience-page-rel|x-dash-dashboard-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '0067075a99b665a7ccfbdff39861a50c'
                    }
                    'aiux-experience-page-rel|x-dash-dashboards-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '999b3dbbedd5cff44ee52180ca12f5f0'
                    }
                    'aiux-experience-page-rel|x-dash-home-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: 'b85a2c25170c73e2f4a2cf8fd40b73ba'
                        deleted: false
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
                    'aiux-m2m-widget-dep|x-dash-board|x-dash-chart.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '215dcd8377c118e90dfc7aff83b7d2a4'
                    }
                    'aiux-m2m-widget-dep|x-dash-chart-tile|x-dash-chart.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '1ea4e661dc5024ff8013959cb5c2865e'
                    }
                    'aiux-m2m-widget-dep|x-dash-dashboard-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '48f33ae6ff2b6e873acfb099e9479810'
                    }
                    'aiux-m2m-widget-dep|x-dash-dashboards-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '43eefd4f183434abdd0218e177b4aa05'
                    }
                    'aiux-m2m-widget-dep|x-dash-home-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '3dc2873862c99f6b4f1bb777ab0db68e'
                        deleted: false
                    }
                    'aiux-m2m-widget-dep|x-dash-settings-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: 'b505fdfbbdc56d49d0403eca5fea36bb'
                    }
                    'aiux-page-widget|x-dash-dashboard-page': {
                        table: 'sys_aix_widget'
                        id: '34fd217bebe2053609bb073aa614c7e5'
                    }
                    'aiux-page-widget|x-dash-dashboards-page': {
                        table: 'sys_aix_widget'
                        id: '8f5de0d6469264f5c52ad2f9ddee34c4'
                    }
                    'aiux-page-widget|x-dash-home-page': {
                        table: 'sys_aix_widget'
                        id: '62aace435216d9f5ad5cc6c270bf46f0'
                        deleted: false
                    }
                    'aiux-page-widget|x-dash-settings-page': {
                        table: 'sys_aix_widget'
                        id: 'c81cda5a047a87d09bce6256def2c0a3'
                    }
                    'aiux-page|x-dash-dashboard-page': {
                        table: 'sys_aix_page'
                        id: 'a19ff7d724cc0138b4b3dbe8638094a8'
                    }
                    'aiux-page|x-dash-dashboards-page': {
                        table: 'sys_aix_page'
                        id: 'ca923ed6ccf09a69d109528387b26fe7'
                    }
                    'aiux-page|x-dash-home-page': {
                        table: 'sys_aix_page'
                        id: '55ccfba069eea3f6eba8c5c82b408a5f'
                        deleted: false
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
                    'aiux-widget|x-dash-chart-tile': {
                        table: 'sys_aix_widget'
                        id: 'dee0e5edc038cf90982150661441f4fc'
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
                        id: '4b6a9abc00ee40d38208b50a139503c3'
                    }
                    'allowed-task': {
                        table: 'x_steas_dash_allowed_table'
                        id: '7736218ed1b54e12949845c23928a65c'
                    }
                    bom_json: {
                        table: 'sys_module'
                        id: '05fae0cdefae40849ac654f0e8080a7b'
                    }
                    package_json: {
                        table: 'sys_module'
                        id: '7f516eef1b274e55a1da5b053d017a3f'
                    }
                    'sample-chart-category': {
                        table: 'x_steas_dash_chart'
                        id: '6f93183382f54903b96b349483d47e5f'
                    }
                    'sample-chart-heat': {
                        table: 'x_steas_dash_chart'
                        id: '69f83faf80fa429ca84c6e5d25473c71'
                    }
                    'sample-chart-open': {
                        table: 'x_steas_dash_chart'
                        id: '2391292c0aba4444ab39236abfa8352f'
                    }
                    'sample-chart-priority': {
                        table: 'x_steas_dash_chart'
                        id: 'f78c14481ae74e61b7f27b89d591ad17'
                    }
                    'sample-chart-state': {
                        table: 'x_steas_dash_chart'
                        id: '858c57bdabab4b7aa5926c33e1d233cc'
                    }
                    'sample-dashboard': {
                        table: 'x_steas_dash_dashboard'
                        id: 'dd8c8d05ca544672b11ebd5c4e415e11'
                    }
                }
                composite: [
                    {
                        table: 'sys_documentation'
                        id: '057993b9eec04c52a6db561b2a8d8fe0'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'order'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact_m2m'
                        id: '0742f34bddd244c087bef59ee873eb2e'
                        key: {
                            application_file: '3afc4a928b989a357c8f0a35607dfbf1'
                            source_artifact: '3771880f193749db91689ee63df5162d'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '077413591635430b8a7c0f3467e88ef9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'title'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '07c6952a29394e1b986ffa0031b43468'
                        key: {
                            sys_security_acl: '319d2f11a0f74c19b6d8f161059f9bba'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '07cf578f55664ab9be3bee12a632ecbe'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0975871944a442e5a1c50f9ec195e19e'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0a72fb2805ea4447a30fc78d2077c094'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'apply_as_filter'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '0b112e0b33844f248d92533df6de5c1e'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '0b460d3199c1463cb4f00f503db4cfa3'
                        key: {
                            sys_security_acl: 'eedfa4d6be514f0a9df3becc128bbdf0'
                            sys_user_role: {
                                id: 'c0e89a2370dd4f0e910866143c99cce3'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0be16b8d44c34410a631886984c6506a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '0c41658588434da5a92581e815de8bc6'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'AVG'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0e21942593d44be3b33ba3e9adedc65c'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'max_groups'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '0e966dafc4554a4fb38508dea4457eaf'
                        key: {
                            sys_security_acl: 'cef3882bcf7d4a869b2baa12308090dc'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0f2e0c0fe1764c15a6b74d05b0d3d147'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '1750726e934a466ebb13eed019bc734f'
                        key: {
                            sys_security_acl: 'bf14b1498c4c4072b5cf1fc6f78bf64c'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '176b371c8bdf4a239e5a8efe78501f67'
                        key: {
                            sys_security_acl: '9d457858f88c47c4a8e41b09fff9918a'
                            sys_user_role: {
                                id: 'c0e89a2370dd4f0e910866143c99cce3'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '17f731929202454b986459ca9840802a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '1836aef7e056405b9a95be0f3a732b19'
                        key: {
                            sys_security_acl: '790d4d824b9449118e63f7102708c877'
                            sys_user_role: {
                                id: 'a3876f2ddbd549058d3bbe9056ea8874'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '1bf3c6bd83804857a687196be0e343a9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_props'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: '1ef995253f9d4cdfb33ec0cc613bd149'
                        key: {
                            name: 'x_steas_dash.builder'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '2246f53058df4b649268060a47d7fbb0'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'shared'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '23cfaabfde78451283e4a7822ea515ad'
                        key: {
                            name: 'x_steas_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '285676f5f16c4009b3333649b71e38ad'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '2860ffe232354b4f83cabdfee5c987c8'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'stacked'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '2bc1cc74f6fa43eab696ddf4115a173f'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Month'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '2e0e503a41434783bf1f96b839258d47'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'query'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '315460143d054fa2b30f6769bd456e90'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '31a10698581d4cd2a0927d661538eb7b'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'order'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '3217b65dd12e4415a4289a9a6404b5a9'
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
                        id: '3223dac9fa414f2f83a13a9138f98822'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '32f9d27c0af14f9eb391b9dda5703773'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'MAX'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact'
                        id: '3771880f193749db91689ee63df5162d'
                        key: {
                            name: 'aiux-source 3afc4a928b989a357c8f0a35607dfbf1'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '383efe49ccf842d8b58b2b24881a39b6'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'list_fields'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '3d23a9217c3141d59fbfe84c07c9d710'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'secure_count'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '3fa01ca973744a8ab7615b6602d34ae6'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'secure_count'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '4109d13fd23e4d3ca3170070f3028d59'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by_2'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '416cd6e7f5314601aac9894ef0c98eed'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'description'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '44f3ccbc03484fa4924c01318509c8d5'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'owner'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '467ce2bf6bf54926b762508291922ed8'
                        key: {
                            sys_security_acl: 'aacc2de2954d45a0b49f00b71907e4fe'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '4b431eb5895943b8bfa5a438b80b4ed2'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'SUM'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '4cf17f44f92246fa9a46007179fb40a4'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'bar'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '4e61df47b9ee4d99b939b506b65ccba8'
                        key: {
                            sys_security_acl: 'af95ca266f0c4284bbe46526356851a7'
                            sys_user_role: {
                                id: '8b633f939c2245f98877cde8c84001f3'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '5016bef992164228a643d1204c397dbc'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Week'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_index'
                        id: '526188d8320641ebb5d7c9d9b73dc996'
                        key: {
                            logical_table_name: 'x_steas_dash_allowed_table'
                            col_name_string: 'source_table'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '5404e287dfa84ee382f1e558e1747ea5'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'area'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '5662425ab1fe492781ccbfafa4acf4d2'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Day'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '57fb039c599f47a38612448780d6b19c'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'name'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: '595e1bfa7a044e89ac4c1274e67b43e4'
                        key: {
                            role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                            contains: {
                                id: '8b633f939c2245f98877cde8c84001f3'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '5a92dbe440844980b148f6862d0589da'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '5d266865002d4233a079107d5f51eae4'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'follow_filters'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '5dce46f4c6904a188773b546b748eac4'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'dashboard'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '610bfc277b244a07aa8862be02195a59'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '649093ce91a1413d93421ec73c2c355d'
                        key: {
                            name: 'x_steas_dash_chart'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '6608ba5d7a574179980cf15a6d870fde'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'MIN'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '688cd574b2664ff78d6ff8ac3babc027'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '6e969b10c85747c5a5cc4fe4eea8b79c'
                        deleted: false
                        key: {
                            sys_security_acl: 'a7f8ea7bea9a4c53ad30d571453b7fc1'
                            sys_user_role: {
                                id: 'a3876f2ddbd549058d3bbe9056ea8874'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '71c8a4343c7a44e687e4ac7997588ab1'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'heatmap'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '71cb0c837b3d456b9992e6a1168069b9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '74ed2d3fc4f547d09e64a5d42fd94fa8'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'line'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: '754e48c6d49b4342897bcac561e4b8ec'
                        key: {
                            role: {
                                id: 'c0e89a2370dd4f0e910866143c99cce3'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                            contains: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '7770e37ade0d431aafa6d2f55e85e2a4'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '79fde8fe0a6b46edbf32a3b6380f60e9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '7d83d18fcd2f4e4798173f078eec808e'
                        key: {
                            sys_security_acl: 'ac392cfdb27e4df4937c22d6b56edc20'
                            sys_user_role: {
                                id: 'c0e89a2370dd4f0e910866143c99cce3'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '7e7b61cc9fae49bfb4226b7a6b74aefb'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'score'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '80696258f6f2461a9dc7bfc5e08921f3'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate_field'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '81040fdbe54d45ecb52c7314c5109550'
                        key: {
                            sys_security_acl: 'bb7694804d9c4bce88de9a32d8242554'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '8231ec905a9c4f3e8058ab9aaa7a60f2'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '829b0212c9964ea1a83c2bef82d314b9'
                        key: {
                            sys_security_acl: '4c0b81598a3f485cab324d7b09f01d5a'
                            sys_user_role: {
                                id: '8b633f939c2245f98877cde8c84001f3'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '8740a4aeaaac4f74a441af680390bfa9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'query'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '89012e85adbc40b7b71e28da4d603b14'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'width'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: '8b633f939c2245f98877cde8c84001f3'
                        key: {
                            name: 'x_steas_dash.viewer'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '8ebc2208d5bb49338820bcab7ff17d88'
                        key: {
                            sys_security_acl: '6c9b25932b0849448f972a6c776da7af'
                            sys_user_role: {
                                id: '8b633f939c2245f98877cde8c84001f3'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '9232304490294f2997b76aa5335a945d'
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
                        id: '92b77bd77da24b2c9c2382ceb6b05ab9'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '933461b7a5404853a6fc29518b7310c8'
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
                        id: '9354efc63eac4f56ba4c94e67852a207'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'width'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '9a21f3c69876471ab4e007492233751c'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate_field'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '9b6f158bb374477798bf3ce793ff5c8c'
                        key: {
                            sys_security_acl: '5932a844addb44f6a0bdf61e21b9b8e1'
                            sys_user_role: {
                                id: '8b633f939c2245f98877cde8c84001f3'
                                key: {
                                    name: 'x_steas_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'a78f3a03387141439782061ab4088e75'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'owner'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'a8cc00d970e34638bc8439a2dd2073db'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'b380ba4858184c689d327b6903ffd0d9'
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
                        id: 'b6708b7ddaa64563a93e8a8b4c15ecad'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'b6a684e64edf45ee914e45773ddfe5a0'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'description'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'b8c797ea4977475880c7b1f12733a324'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'list'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'bb8a4d3d74b94fdc9726d70052b1a6ef'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'bf66860364e347e7b9685bbac1ce114a'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'dashboard'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: 'c0e89a2370dd4f0e910866143c99cce3'
                        key: {
                            name: 'x_steas_dash.admin'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'c487772c302446128de63e7cb1664e76'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'apply_as_filter'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'c4d6adf015174c04ae5c98c0369cfca4'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'max_groups'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c5a55fd8e8a44b6d933caaf5d9577583'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'list_fields'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'c5bf4f1c5d584bc78e4746e2b9bafb65'
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
                        id: 'ca0e94c1093d42e69852cbe6d1e73752'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'group_by_2'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'd0b63fb5e64442e1a6c8a64df0ee91c3'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'd0e8ce86a3354beca2b2da403ccdbfe5'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'follow_filters'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'd2adf41e4ad4479c9c02c0038a05e27b'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                            value: 'filter'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'd77ce99fb5fb4be89cdf105e2b92e7ab'
                        key: {
                            sys_security_acl: '6adf7eae6bef46a68e25b3d7672eeaa5'
                            sys_user_role: {
                                id: '1ef995253f9d4cdfb33ec0cc613bd149'
                                key: {
                                    name: 'x_steas_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'd7e54e19f7354f80898aa46010fc7279'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'grid_props'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'd8f4bfcea98b49f6a3528fc02c37e6fe'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'dba136a50cb34c44942bad0daff0b3ee'
                        key: {
                            sys_security_acl: '8096bad983644bc18610d9ea8cd11a8e'
                            sys_user_role: {
                                id: '9fb04703dfae462fb413079f5b425fb2'
                                key: {
                                    name: 'x_steas_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'e417bbd52144488cb7ffc99873cfcd0b'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            language: 'en'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: 'e61c6197cc1148e6adb6231dca2e8794'
                        key: {
                            name: 'x_steas_dash_chart'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'ed3a58d5764b497ca7bd1c255de2de8b'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'trend'
                            value: 'Quarter'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'edc6259007204f19b9103ceea4c1964c'
                        key: {
                            name: 'x_steas_dash_allowed_table'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f1b214584de1421d8574781f7a9d2159'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f30330c85bea4d689f7141a95a484710'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'title'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f42d913ef0bd440b969cd5e7edcbff4c'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'name'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'f5582d1cca5b403ebd3fb3eb23e32062'
                        key: {
                            name: 'x_steas_dash_dashboard'
                            element: 'shared'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: 'f5ecbf43affa45d5a0c2e902284d6c70'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: 'f8b7bcb5ec14430d8e2cf13c0c3cfc21'
                        key: {
                            name: 'x_steas_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: 'fe73f75d549f4180b32b19163c2615bd'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'fedc1af33b2e4d6aaeb4637271bb90b5'
                        key: {
                            name: 'x_steas_dash_chart'
                            element: 'aggregate'
                            value: 'COUNT'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                ]
            }
        }
    }
}
