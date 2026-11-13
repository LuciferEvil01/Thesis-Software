<?php
// Foto del entorno Moodle (versión, PHP, base de datos, configuración, plugins).
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
global $DB, $CFG;
$counts = [];
foreach (core_plugin_manager::instance()->get_plugins() as $type => $items) {
    $counts[$type] = count($items);
}
echo json_encode([
    'generated_at' => gmdate(DATE_ATOM),
    'moodle' => ['release' => $CFG->release, 'version' => $CFG->version, 'branch' => $CFG->branch],
    'php' => ['version' => PHP_VERSION],
    'database' => ['family' => $DB->get_dbfamily(), 'server' => $DB->get_server_info()],
    'configuration' => ['wwwroot' => $CFG->wwwroot, 'lang' => current_language(), 'timezone' => $CFG->timezone,
        'enablecompletion' => (bool)$CFG->enablecompletion, 'enablewebservices' => (bool)$CFG->enablewebservices],
    'plugins_by_type' => $counts,
    'local_alertatemprana' => core_plugin_manager::instance()->get_plugin_info('local_alertatemprana')?->versiondb,
    'cron' => ['lastcron' => get_config('tool_task', 'lastcronstart')],
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . PHP_EOL;
