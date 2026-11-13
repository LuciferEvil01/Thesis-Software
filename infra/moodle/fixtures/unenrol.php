<?php
// Desmatricula estudiantes de un curso (simula bajas a lo largo del tiempo en el laboratorio).
//   php unenrol.php <idnumber del curso> <usuario> [<usuario> ...]
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->libdir . '/enrollib.php');
global $DB;
\core\session\manager::set_user(get_admin());
$course = $DB->get_record('course', ['idnumber' => $argv[1]], '*', MUST_EXIST);
$instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
$manual = enrol_get_plugin('manual');
$done = 0;
foreach (array_slice($argv, 2) as $username) {
    $user = $DB->get_record('user', ['username' => $username, 'deleted' => 0]);
    if ($user && $DB->record_exists('user_enrolments', ['enrolid' => $instance->id, 'userid' => $user->id])) {
        $manual->unenrol_user($instance, $user->id);
        $done++;
    }
}
echo json_encode(['courseid' => (int)$course->id, 'unenrolled' => $done]) . PHP_EOL;
