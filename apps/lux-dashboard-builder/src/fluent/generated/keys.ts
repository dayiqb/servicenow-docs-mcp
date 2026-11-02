import '@servicenow/sdk/global'

declare global {
    namespace Now {
        namespace Internal {
            interface Keys extends KeysRegistry {
                explicit: {
                    'acl-allowed-create': {
                        table: 'sys_security_acl'
                        id: 'ac866248e8ac4cbeb8c4c2aaea74207b'
                    }
                    'acl-allowed-delete': {
                        table: 'sys_security_acl'
                        id: '1d5781d417e0403cb6f532d4a4a74d12'
                    }
                    'acl-allowed-read': {
                        table: 'sys_security_acl'
                        id: '4bf71f0d1a0740c49d87f8909766c3d3'
                    }
                    'acl-allowed-write': {
                        table: 'sys_security_acl'
                        id: '2ac89d48178649c1844908c9dc3b1c0a'
                    }
                    'acl-chart-create': {
                        table: 'sys_security_acl'
                        id: '2d14a74865d5479da623fec21e01df38'
                    }
                    'acl-chart-delete': {
                        table: 'sys_security_acl'
                        id: '59712a3a9d9a44be9e7c80a159aaa5b7'
                    }
                    'acl-chart-read': {
                        table: 'sys_security_acl'
                        id: 'f720741bc1c34e20b11229d4da877bc3'
                    }
                    'acl-chart-write': {
                        table: 'sys_security_acl'
                        id: '3ecc8f03aeb24597ad915687d8adab10'
                    }
                    'acl-dashboard-create': {
                        table: 'sys_security_acl'
                        id: 'c6adaa0f720444f9b5af93dc62f3d3f3'
                    }
                    'acl-dashboard-delete': {
                        table: 'sys_security_acl'
                        id: '037683a9f893436dacdbf07ef9355190'
                    }
                    'acl-dashboard-read': {
                        table: 'sys_security_acl'
                        id: 'c7c7e80cc19144c9b331ec6ad871c69e'
                    }
                    'acl-dashboard-write': {
                        table: 'sys_security_acl'
                        id: 'c6b7d832c5b949d1a127a1bad50a4298'
                    }
                    'aiux-acl|x-dash-dashboard-page|read|allow_if|x_dash.viewer': {
                        table: 'sys_security_acl'
                        id: '041467595db1443192f1be29a6cc9377'
                    }
                    'aiux-acl|x-dash-home-page|read|allow_if|x_dash.viewer': {
                        table: 'sys_security_acl'
                        id: '8e3aa769698e44a2a097e3336cb38dcc'
                    }
                    'aiux-acl|x-dash-settings-page|read|allow_if|x_dash.admin': {
                        table: 'sys_security_acl'
                        id: 'cdc69ce06bfb4b559f4395f0d308ee7c'
                    }
                    'aiux-color-swatch|lux-dashboard-builder': {
                        table: 'sys_aix_color_swatch'
                        id: 'ebf1dd7e7ccae1ef08a33182d722c80f'
                    }
                    'aiux-dependency|document-title.js': {
                        table: 'sys_aix_dependency'
                        id: 'dc67cdbb7ba080f744666af81e325830'
                    }
                    'aiux-experience-page-rel|x-dash-dashboard-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '45cd80a84f6ff8516a9047f65ee68e79'
                    }
                    'aiux-experience-page-rel|x-dash-home-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '65be45e42c21b11add6cef20486fa59b'
                    }
                    'aiux-experience-page-rel|x-dash-incidents-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: '47ddfcdd8102baed76872ad23ce90d8b'
                        deleted: true
                    }
                    'aiux-experience-page-rel|x-dash-settings-page': {
                        table: 'sys_aix_experience_page_rel'
                        id: 'f5d2084465d2d743138dc19d907089b8'
                    }
                    'aiux-experience-prop|appHeadCss': {
                        table: 'sys_aix_experience_properties'
                        id: 'feaa7675c9ea749a1b0edaacab00d5ff'
                    }
                    'aiux-experience-prop|appTailwindCss': {
                        table: 'sys_aix_experience_properties'
                        id: '961b1bd22ce7bc447c16d69d3deb213a'
                    }
                    'aiux-experience|lux-dashboard-builder': {
                        table: 'sys_aix_experience'
                        id: 'f70b71519345a798c2b0a02903563d08'
                    }
                    'aiux-layout-widget|lifecycle': {
                        table: 'sys_aix_widget'
                        id: '08231862ac6498d15ef62131ac67bd25'
                    }
                    'aiux-m2m-widget-dep|x-dash-dashboard-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: '11676dab2a7f87e026231253b2fd6576'
                    }
                    'aiux-m2m-widget-dep|x-dash-home-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: 'f425114bded67119f9ad3da459a0a247'
                    }
                    'aiux-m2m-widget-dep|x-dash-settings-page|document-title.js': {
                        table: 'sys_aix_m2m_widget_dependency'
                        id: 'c2aefe26cd922bcecefc54365ebe8544'
                    }
                    'aiux-page-widget|x-dash-dashboard-page': {
                        table: 'sys_aix_widget'
                        id: '7ba7b7eddda40e9002bc68b151f28668'
                    }
                    'aiux-page-widget|x-dash-home-page': {
                        table: 'sys_aix_widget'
                        id: '9b7e1037af15fd5545d7c039f3ec8b7a'
                    }
                    'aiux-page-widget|x-dash-incidents-page': {
                        table: 'sys_aix_widget'
                        id: '272e83dfc82322a7b2b1c5f5bd57e9c6'
                        deleted: true
                    }
                    'aiux-page-widget|x-dash-settings-page': {
                        table: 'sys_aix_widget'
                        id: '40e64052ed22b5c499aa70e211f08745'
                    }
                    'aiux-page|x-dash-dashboard-page': {
                        table: 'sys_aix_page'
                        id: '1ee1f423cf332bfad377b6c275baae39'
                    }
                    'aiux-page|x-dash-home-page': {
                        table: 'sys_aix_page'
                        id: '068dd1afc5916fc966ebc27aa9face5e'
                    }
                    'aiux-page|x-dash-incidents-page': {
                        table: 'sys_aix_page'
                        id: 'a34292a3f32a4e04936134df874ed777'
                        deleted: true
                    }
                    'aiux-page|x-dash-settings-page': {
                        table: 'sys_aix_page'
                        id: '45c3a9c2f09327d5ef0fba1a4a199e49'
                    }
                    'aiux-project|x_dash': {
                        table: 'sys_aix_project'
                        id: 'da1bb9d8827e891ea5dd36dec4d29c60'
                    }
                    'aiux-theme|lux-dashboard-builder': {
                        table: 'sys_aix_theme'
                        id: '68900d4a8f9124cec61097db9b02792c'
                    }
                    'aiux-widget|aiux-hello-world': {
                        table: 'sys_aix_widget'
                        id: '561bcca65337af0955e8924112508c34'
                        deleted: true
                    }
                    'aiux-widget|x-dash-board': {
                        table: 'sys_aix_widget'
                        id: '7cc6d658b2f8c8a5b370917d25d5f6a7'
                    }
                    'aiux-widget|x-dash-dashboards': {
                        table: 'sys_aix_widget'
                        id: '8457c847d209ef232796326adc41c988'
                    }
                    'aiux-widget|x-dash-settings': {
                        table: 'sys_aix_widget'
                        id: '153d702e0712323064adf34fda538fe7'
                    }
                    'allowed-incident': {
                        table: 'x_dash_allowed_table'
                        id: 'dceea6232b954b9ab541a5aaac02dd46'
                    }
                    'allowed-task': {
                        table: 'x_dash_allowed_table'
                        id: '72915f8f2eca4250b61d5822aea74aeb'
                    }
                    bom_json: {
                        table: 'sys_module'
                        id: '6bcb9a10c9af41a49f1e3c9d91af8d36'
                    }
                    package_json: {
                        table: 'sys_module'
                        id: '53f277cc777648449992c62ae4d40941'
                    }
                    'sample-chart-category': {
                        table: 'x_dash_chart'
                        id: 'c18f18ef7da0401988c9712646b6c4b1'
                    }
                    'sample-chart-heat': {
                        table: 'x_dash_chart'
                        id: 'c0d9a0d04ab047ef8069457a0e189322'
                    }
                    'sample-chart-open': {
                        table: 'x_dash_chart'
                        id: 'e452094705734a4bb1e542f2ceef3470'
                    }
                    'sample-chart-priority': {
                        table: 'x_dash_chart'
                        id: '9e5a9a8aba484b0594433297a4c33f11'
                    }
                    'sample-chart-state': {
                        table: 'x_dash_chart'
                        id: 'cdf6880bb0944ed7af58d752e6bafced'
                    }
                    'sample-dashboard': {
                        table: 'x_dash_dashboard'
                        id: 'f0b5ce7aac2842aaa8e88446556a558a'
                    }
                }
                composite: [
                    {
                        table: 'sys_choice'
                        id: '012ff2e6fa8848b0b595a0d225e59b29'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            value: 'AVG'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '0b33af2523fd4676aaee55b23e998e28'
                        key: {
                            name: 'x_dash_chart'
                            element: 'width'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '0d24453b302146c1b76acf4bd07ac41e'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '0d98d5d355f94dadb4872a4c2a2d7a3a'
                        key: {
                            name: 'x_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '12590d2ba76c4877aec75bf935b8558e'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '12f7cbe8962d4f17829ccd1dfd723b8d'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '14c0d17ad954490998cb70fea20173b2'
                        key: {
                            name: 'x_dash_chart'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '15a1227c512e4c6188efc60f7aaaea86'
                        key: {
                            name: 'x_dash_chart'
                            element: 'group_by'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '1649d9fdf0b748dbbcd4077528ba1f81'
                        key: {
                            sys_security_acl: '037683a9f893436dacdbf07ef9355190'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: '1c892d833c864f8aaa3e6e9646163bf6'
                        key: {
                            name: 'x_dash.admin'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '1d0fa5464a7d4c659c18951ac2f3d426'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'pie'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '228b7f0e29e54b3a8e97fe37944123fb'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'description'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '2583ff0f0d1b4ebda5be169217fcab99'
                        key: {
                            sys_security_acl: '2ac89d48178649c1844908c9dc3b1c0a'
                            sys_user_role: {
                                id: '1c892d833c864f8aaa3e6e9646163bf6'
                                key: {
                                    name: 'x_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '2a0ed40bfdb74a859490035d895631a6'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate_field'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '2a8f1ebda85d4557b5c6631ce917de44'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'bar'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '2bcfc42d6bde4abbb58b393c718161e2'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '2ea16e64b7fe4ce298fdde34b82e007a'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'Week'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '2fb47992127f40539b2508b4bf609529'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '2ff0513581604788bd493d13cd0f9190'
                        key: {
                            sys_security_acl: 'f720741bc1c34e20b11229d4da877bc3'
                            sys_user_role: {
                                id: 'd86b1f81b4f74b36992c4e48c6aa627a'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: '31357e6db4f14dddb01db8bb41c62a38'
                        key: {
                            name: 'x_dash_chart'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '349b556640ed4aeeb99f5d3738ac12fd'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'owner'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '35d25c16d6584c30aab9b2658ac00c0a'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'none'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '3610febc582e49d086649827fc54260c'
                        key: {
                            sys_security_acl: '2d14a74865d5479da623fec21e01df38'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '3958d3d90a92492b8880d5c8ff4c4277'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '3b2600ed773543fa9c47a8899c1d7ccb'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'shared'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '3b5900526da245e9a59d885cd0c8aab5'
                        key: {
                            sys_security_acl: 'c6b7d832c5b949d1a127a1bad50a4298'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '3cd3fa147b6749fb958654322bd09c97'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            value: 'MAX'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '43a4188e03944dda9cb0b77f5683f179'
                        key: {
                            sys_security_acl: '4bf71f0d1a0740c49d87f8909766c3d3'
                            sys_user_role: {
                                id: 'd86b1f81b4f74b36992c4e48c6aa627a'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '4527abb1acf748508a9af8539e7bfdb6'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'owner'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '4c763277a9f24495be40c7edd2f9ac9c'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'column'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '4fa8be7463824249b6486ce7b905d0ab'
                        key: {
                            name: 'x_dash_chart'
                            element: 'title'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '523d20da840f4caa944fede3e674d490'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'score'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '53ee3fa7c04a4d1bbdcb9077fbc40d0b'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'Quarter'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '59b16acbc67c42c6b9ebede73b76ffa1'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'stacked'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '5b1cad1362f749d5b0ecaf92ff53bdc0'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'source_table'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '5cf20a13d72341e4a79e8808bd2ee935'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'name'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '5ddc99fc8d964c73a907afb914e93ec9'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'line'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: '5e2d91b9cc94455fbe87a1a1381a072f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '5ed906b522db41b3aff516d036f86cc0'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'description'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '622a8e9157654d378e0f5b4f0b2931ce'
                        key: {
                            sys_security_acl: 'cdc69ce06bfb4b559f4395f0d308ee7c'
                            sys_user_role: {
                                id: '256455f3af0846dfb07a0d376c460f64'
                                key: {
                                    name: 'x_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '636a9c1cfc7742a5861d6ad5b657523d'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'shared'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '6d82eaa9974d4c86aedb7569e422a483'
                        key: {
                            sys_security_acl: 'c6adaa0f720444f9b5af93dc62f3d3f3'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '6d843d7f6e85474fbc7f9d920f42b403'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            value: 'MIN'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '79047864621448e9a4b18c2ed8afccc4'
                        key: {
                            name: 'x_dash_chart'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '7b7298f34ed9462c868cda4bf914bb86'
                        key: {
                            name: 'x_dash_chart'
                            element: 'title'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '7e62ca8a824847c7bee8c9341a780fb8'
                        key: {
                            name: 'x_dash_chart'
                            element: 'list_fields'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '834b9d55b36e4dc5869194914ad32818'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '8d3b7bb97c94414b90c72375210752fc'
                        key: {
                            sys_security_acl: '59712a3a9d9a44be9e7c80a159aaa5b7'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '908b3ac37e2a4a21a753b049e49f3318'
                        key: {
                            name: 'x_dash_chart'
                            element: 'query'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: '9444a2c969134a5eaab028af1596d27a'
                        key: {
                            sys_security_acl: 'ac866248e8ac4cbeb8c4c2aaea74207b'
                            sys_user_role: {
                                id: '1c892d833c864f8aaa3e6e9646163bf6'
                                key: {
                                    name: 'x_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '96455139aaab460f9c2965be0bdafd81'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: '980a9a9d8c1d4898aec79b6098ad1edd'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: '9ab0c79f62eb4ba981ce5a4317b05fd5'
                        key: {
                            role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                            contains: {
                                id: 'd86b1f81b4f74b36992c4e48c6aa627a'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: '9b9772d61df94bd18bb1135f50a21439'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'heatmap'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact_m2m'
                        id: '9d043942d606467abbd3bc28cf030c02'
                        key: {
                            application_file: 'da1bb9d8827e891ea5dd36dec4d29c60'
                            source_artifact: 'b3f5ed0ffd354cf8a79e36db8d4d0ae6'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: '9dda852a09654177bdeaebdf8998a625'
                        key: {
                            name: 'x_dash_chart'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: '9f6984fb972443faac9ebcb63b78e1fd'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate_field'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'a35f135311db422183b86f788e8cc5fc'
                        key: {
                            name: 'x_dash_chart'
                            element: 'list_fields'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'a36ae20428094e47a780a9f9a6138081'
                        key: {
                            name: 'x_dash_chart'
                            element: 'max_groups'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'a80d849387174117b4ee5aa1798cf23f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'order'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'a8bbc87f1ff2477a9dbfebcc43fb8150'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'name'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'a9b2b0306cd34c18becf49135ceaab60'
                        key: {
                            name: 'x_dash_chart'
                            element: 'dashboard'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'ad440f64d4a246239ff4818de9819b4f'
                        key: {
                            sys_security_acl: '3ecc8f03aeb24597ad915687d8adab10'
                            sys_user_role: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: 'b01f921ca35b4e3aa5a85140cb041a67'
                        key: {
                            name: 'x_dash_dashboard'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'b035b40623c34fc8be30db93e5713cee'
                        key: {
                            sys_security_acl: '041467595db1443192f1be29a6cc9377'
                            sys_user_role: {
                                id: '006c90f038ee42f69ec824acc13450e8'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_index'
                        id: 'b35ff205deb24bb09a995c4ed58efd83'
                        key: {
                            logical_table_name: 'x_dash_allowed_table'
                            col_name_string: 'source_table'
                        }
                    },
                    {
                        table: 'sn_glider_source_artifact'
                        id: 'b3f5ed0ffd354cf8a79e36db8d4d0ae6'
                        key: {
                            name: 'aiux-source da1bb9d8827e891ea5dd36dec4d29c60'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'b68ae859ac9b46058e55b27b48e1a71f'
                        key: {
                            sys_security_acl: 'c7c7e80cc19144c9b331ec6ad871c69e'
                            sys_user_role: {
                                id: 'd86b1f81b4f74b36992c4e48c6aa627a'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'b759648c7ac546aa9233b00535d7ccd0'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'bb36ad993dbe4c58bd561f94a033992f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            value: 'COUNT'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'bc1a0ce3d61749f081f8e923a58fa6b0'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'active'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'bd7d78edfc9a4a1c86492455cb6c01a6'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'Month'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'be56eb278abc4e08919ab3f0cdbbedcb'
                        key: {
                            name: 'x_dash_chart'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'be5ff021527f41b8b33b9272d4eeb975'
                        key: {
                            name: 'x_dash_chart'
                            element: 'group_by'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'bff1302600bb4247b3c3d57a39f06f24'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'active'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'c0ebe217c59142ecafbc6a567d4fbfac'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'Day'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c2e3cbc92b674dcc9c0452cae10e55f6'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice_set'
                        id: 'c3499878d4ff40e8a608ace09efac56f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'c4da3a2ed7154773a61b69e6039c96e4'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'donut'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'c7ee007487d3427fb0f51949e2286592'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'c96b9456e3e24bf7b6229bda1839e04c'
                        key: {
                            name: 'x_dash_chart'
                            element: 'group_by_2'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'cef54dc82bc946b9a356a6bc82a63338'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'source_table'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'cfd0a28436c44a0fabc1f28def92c1a9'
                        key: {
                            name: 'x_dash_chart'
                            element: 'width'
                            language: 'en'
                        }
                    },
                    {
                        table: 'ua_table_licensing_config'
                        id: 'd4e2e5f42d7f4b1f94d335897c18e7c2'
                        key: {
                            name: 'x_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: 'd86b1f81b4f74b36992c4e48c6aa627a'
                        key: {
                            name: 'x_dash.viewer'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'd980dd1dd92645d29cb2d1392121e477'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'secure_count'
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'e16b64940a444503b15cebd8044a30b2'
                        key: {
                            name: 'x_dash_dashboard'
                            element: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'e1856b70019b4a51a51b1e4bb977ee27'
                        key: {
                            sys_security_acl: '1d5781d417e0403cb6f532d4a4a74d12'
                            sys_user_role: {
                                id: '1c892d833c864f8aaa3e6e9646163bf6'
                                key: {
                                    name: 'x_dash.admin'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'e2331656e2c946b08df2632aeefcec9b'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'list'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'e37acfbdd31343d4b881689d6bde9b10'
                        key: {
                            name: 'x_dash_chart'
                            element: 'dashboard'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'e38f7c2e0c26419185c096701435396f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'order'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'e43721f4eccc4c8ba33fe3d18b4d772e'
                        key: {
                            name: 'x_dash_chart'
                            element: 'trend'
                            value: 'Year'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'e442d007f875446ea6a3b70364534e7f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'chart_type'
                            value: 'area'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'e484f175f09540dea4156af908581c95'
                        key: {
                            name: 'x_dash_chart'
                            element: 'query'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_choice'
                        id: 'e60485625b134202b532a8d91b9dcfbb'
                        key: {
                            name: 'x_dash_chart'
                            element: 'aggregate'
                            value: 'SUM'
                            language: 'en'
                            dependent_value: 'NULL'
                        }
                    },
                    {
                        table: 'sys_security_acl_role'
                        id: 'e9a2f2d1289e465fae13536e22fb30db'
                        key: {
                            sys_security_acl: '8e3aa769698e44a2a097e3336cb38dcc'
                            sys_user_role: {
                                id: '006c90f038ee42f69ec824acc13450e8'
                                key: {
                                    name: 'x_dash.viewer'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'ed98f42ab7d84b7bb14c18b1b742c3e5'
                        key: {
                            name: 'x_dash_allowed_table'
                            element: 'secure_count'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_user_role_contains'
                        id: 'edf68262a7474e2e8840f604579e8087'
                        key: {
                            role: {
                                id: '1c892d833c864f8aaa3e6e9646163bf6'
                                key: {
                                    name: 'x_dash.admin'
                                }
                            }
                            contains: {
                                id: 'f59decb7efd046108fa6745d41373563'
                                key: {
                                    name: 'x_dash.builder'
                                }
                            }
                        }
                    },
                    {
                        table: 'sys_dictionary'
                        id: 'f11accb97a4b401fa642bf35496ed52f'
                        key: {
                            name: 'x_dash_chart'
                            element: 'group_by_2'
                        }
                    },
                    {
                        table: 'sys_db_object'
                        id: 'f2d7c55076774b7282cf9b1caa5f70d7'
                        key: {
                            name: 'x_dash_allowed_table'
                        }
                    },
                    {
                        table: 'sys_user_role'
                        id: 'f59decb7efd046108fa6745d41373563'
                        key: {
                            name: 'x_dash.builder'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'fa0c985b756b48de942c925254903a20'
                        key: {
                            name: 'x_dash_chart'
                            element: 'max_groups'
                            language: 'en'
                        }
                    },
                    {
                        table: 'sys_documentation'
                        id: 'fc0713aa74db49b2bff703d5443226cc'
                        key: {
                            name: 'x_dash_chart'
                            element: 'NULL'
                            language: 'en'
                        }
                    },
                ]
            }
        }
    }
}
