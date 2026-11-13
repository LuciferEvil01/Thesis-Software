<?php
// Laboratorio: configura el acceso del sistema de alerta temprana con la misma clase que se usaría en
// una instalación real (local_alertatemprana\setup, también en local/alertatemprana/cli/setup.php) y
// escribe las credenciales en /opt/alerta-generated/rest.env (.runtime/generated/rest.env).
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
\core\session\manager::set_user(get_admin());

$password = getenv('MOODLE_TECH_PASSWORD');
if ($password === false || $password === '') {
    throw new RuntimeException('Falta MOODLE_TECH_PASSWORD');
}
$r = \local_alertatemprana\setup::run($password);
file_put_contents('/opt/alerta-generated/rest.env',
    "MOODLE_URL={$r['url']}\nMOODLE_TECH_USER={$r['usuario']}\nMOODLE_TOKEN={$r['token']}\n");
chmod('/opt/alerta-generated/rest.env', 0600);
unset($r['token']);
echo json_encode($r + ['credenciales' => '.runtime/generated/rest.env'], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . PHP_EOL;
