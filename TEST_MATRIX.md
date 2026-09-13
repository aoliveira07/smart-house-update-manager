# Matriz dos cenários obrigatórios

Os testes usam APIs simuladas. A equivalência com cada cenário não constitui aceite
de execução no equipamento real. A suíte completa acrescenta testes de transporte,
WebSocket, configuração, segurança Ingress, contratos legados e falhas de recuperação.

| Nº | Cenário SH-005 | Teste principal |
| --- | --- | --- |
| 01 | Nenhuma atualização | test_daily_reboot_with_or_without_updates[None] |
| 02 | Somente Core | test_individual_update_success[CORE] |
| 03 | Somente OS | test_os_staged_without_immediate_reboot |
| 04 | Somente App | test_individual_update_success[APP] |
| 05 | Somente HACS | test_individual_update_success[HACS_SOFTWARE] |
| 06 | Firmware ignorado | test_manual_categories_ignored[FIRMWARE] |
| 07 | Unknown ignorado | test_manual_categories_ignored[UNKNOWN] |
| 08 | Backup OK | test_backup_confirmed_before_update |
| 09 | Backup falha | test_backup_failure_aborts_updates; test_child_error_fails_backup |
| 10 | Backup timeout | test_backup_timeout_never_installs_even_if_job_later_finishes |
| 11 | Core OK | test_individual_update_success[CORE] |
| 12 | Core falha | test_update_failure[CORE-/core/update] |
| 13 | App OK | test_individual_update_success[APP] |
| 14 | App falha | test_update_failure[APP-/store/addons/test_app/update] |
| 15 | OS OK | test_daily_reboot_with_or_without_updates[OS] |
| 16 | OS falha | test_update_failure[OS-/os/update]; test_os_wrong_version_after_boot_fails |
| 17 | Job às 05:30 | test_job_at_0530_defers_then_reboots |
| 18 | Reboot adiado | test_job_at_0530_defers_then_reboots |
| 19 | Reboot depois do job | test_job_at_0530_defers_then_reboots |
| 20 | Sem update + reboot | test_daily_reboot_with_or_without_updates[None] |
| 21 | Update + reboot | test_daily_reboot_with_or_without_updates[CORE/APP/HACS_SOFTWARE] |
| 22 | OS + único reboot diário | test_daily_reboot_with_or_without_updates[OS] |
| 23 | Reboot falha | test_reboot_rejected; test_busy_timeout_and_notification |
| 24 | Retomada após reboot | test_recover_reboot_after_new_manager |
| 25 | Restart durante rotina | test_app_restart_resumes_backup_job_without_duplicate |
| 26 | Duas rotinas concorrentes | test_concurrent_maintenance_rejected; test_persistent_lock_across_connections |
| 27 | Self-update ignorado | test_self_update_excluded |
| 28 | Dry Run | test_dry_run_has_no_mutations; test_global_dry_run_blocks_manual_reboot |
| 29 | Auto-update nativo habilitado | test_supervisor_native_auto_update[True] |
| 30 | Auto-update nativo desabilitado | test_supervisor_native_auto_update[False]; test_native_auto_update_opt_out |

Os arquivos estão em `tests/`. O resultado bruto da execução está em `TEST_RESULTS.txt`.
