<?php
// Configura el acceso del sistema de alerta temprana y muestra la URL y el token para su archivo .env.
//   php local/alertatemprana/cli/setup.php [--password=CONTRASEÑA]
define('CLI_SCRIPT', true);
require(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/clilib.php');

[$options] = cli_get_params(['password' => null, 'help' => false], ['h' => 'help']);
if ($options['help']) {
    echo "Crea (o actualiza) el usuario alerta_servicio, el servicio alerta_connector y su token.\n" .
        "Opciones: --password=CONTRASEÑA (solo si hay que crear el usuario; si no, aleatoria).\n";
    exit(0);
}
\core\session\manager::set_user(get_admin());
$r = \local_alertatemprana\setup::run($options['password']);
echo "MOODLE_URL={$r['url']}\nMOODLE_TOKEN={$r['token']}\n";
cli_writeln("Usuario {$r['usuario']}, servicio {$r['servicio']} con {$r['funciones']} funciones. " .
    "Copie las dos líneas anteriores al .env del sistema de alerta temprana.");
