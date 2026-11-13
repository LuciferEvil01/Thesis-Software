<?php
// Crea (o recrea) un curso completo a partir de una especificación JSON: estudiantes, recursos,
// evaluaciones, entregas, notas con sus fechas y eventos del registro. Solo para el laboratorio
// local (pruebas de extracción y reproducción de OULAD, PLAN.md F3–F4).
//
//   php seed_course.php /opt/alerta-generated/seed/<curso>.json
//
// Especificación (los días se cuentan desde startdate):
// {
//   "course":   {"idnumber", "shortname", "fullname", "startdate": unix, "length_days"},
//   "teacher":  {"username", "firstname", "lastname"},
//   "service_role": "teacher" | "editingteacher" | null,           // rol del usuario de servicio (por defecto teacher)
//   "students": [{"username", "firstname", "lastname", "withdrawn": bool}],
//   "resources":[{"key", "name"}],                                    // páginas
//   "items":    [{"key", "type": "assign"|"quiz", "name", "due_day", "grademax",
//                 "gradepass"?: nota para aprobar, "online"?: false = tarea sin entregas en línea}],
//   "grades":   [{"username", "item", "submitted_day"|null, "raw"|null, "graded_day"|null}],
//   "activity": [{"username", "day", "site": key|null, "events"}]     // site null = página del curso
// }
// Si ya existe un curso con ese idnumber, se borra y se crea de nuevo. Los estudiantes con
// "withdrawn" se desmatriculan al final (Moodle deja de listarlos, como ocurre con una baja real).
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->libdir . '/enrollib.php');
require_once($CFG->libdir . '/gradelib.php');
global $DB, $CFG;
\core\session\manager::set_user(get_admin());
core_php_time_limit::raise();
raise_memory_limit(MEMORY_HUGE);

$spec = json_decode(file_get_contents($argv[1] ?? 'php://stdin'), true, 512, JSON_THROW_ON_ERROR);
$start = (int)$spec['course']['startdate'];
$at = fn(float $day, int $seconds) => $start + (int)floor($day) * DAYSECS + $seconds;
$password = getenv('MOODLE_DEMO_PASSWORD') ?: 'Demo-Alerta-2026!';

function ensure_user(array $u, string $password): stdClass {
    global $DB, $CFG;
    $existing = $DB->get_record('user', ['username' => $u['username'], 'mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0]);
    if ($existing) {
        update_internal_user_password($existing, $password);  // la contraseña de prueba puede haber cambiado
        if ($existing->firstname !== $u['firstname'] || $existing->lastname !== $u['lastname']) {
            $DB->update_record('user', (object)['id' => $existing->id, 'firstname' => $u['firstname'],
                'lastname' => $u['lastname']]);
        }
        return $existing;
    }
    $id = user_create_user((object)['auth' => 'manual', 'confirmed' => 1, 'mnethostid' => $CFG->mnet_localhost_id,
        'username' => $u['username'], 'password' => $password, 'firstname' => $u['firstname'],
        'lastname' => $u['lastname'], 'email' => $u['username'] . '@alerta.local', 'country' => 'CU'], true, false);
    return $DB->get_record('user', ['id' => $id], '*', MUST_EXIST);
}

function add_module(stdClass $course, string $modname, string $name, string $idnumber, array $extra): stdClass {
    global $DB;
    $module = (object)array_merge([
        'course' => $course->id, 'module' => $DB->get_field('modules', 'id', ['name' => $modname], MUST_EXIST),
        'modulename' => $modname, 'section' => 1, 'name' => $name, 'idnumber' => $idnumber, 'cmidnumber' => $idnumber,
        'visible' => 1, 'intro' => '', 'introformat' => FORMAT_HTML,
    ], $extra);
    return add_moduleinfo($module, $course);
}

// Curso
$c = $spec['course'];
if ($old = $DB->get_record('course', ['idnumber' => $c['idnumber']])) {
    delete_course($old, false);
}
$course = create_course((object)['fullname' => $c['fullname'], 'shortname' => $c['shortname'], 'idnumber' => $c['idnumber'],
    'category' => 1, 'format' => 'topics', 'numsections' => 1, 'visible' => 1, 'enablecompletion' => 1,
    'startdate' => $start, 'enddate' => $start + (int)$c['length_days'] * DAYSECS]);
course_create_sections_if_missing($course, 1);
// Sin mensajes de bienvenida a cada estudiante sembrado
$DB->set_field('enrol', 'customint1', 0, ['courseid' => $course->id, 'enrol' => 'manual']);

// Personas
$studentrole = $DB->get_field('role', 'id', ['shortname' => 'student'], MUST_EXIST);
$teacherrole = $DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST);
$teacher = ensure_user($spec['teacher'], $password);
enrol_try_internal_enrol($course->id, $teacher->id, $teacherrole);
// El servicio de alerta entra en el curso como lo haría con un profesor real: matriculado por él
$servicerole = array_key_exists('service_role', $spec) ? $spec['service_role'] : 'teacher';
if ($servicerole !== null) {
    $service = $DB->get_record('user', ['username' => 'alerta_servicio', 'deleted' => 0], '*', MUST_EXIST);
    enrol_try_internal_enrol($course->id, $service->id, $DB->get_field('role', 'id', ['shortname' => $servicerole], MUST_EXIST));
}
$users = [];
foreach ($spec['students'] as $s) {
    $users[$s['username']] = ensure_user($s, $password);
    enrol_try_internal_enrol($course->id, $users[$s['username']]->id, $studentrole, $start);
}

// Recursos y evaluaciones
$sites = [];  // key → [cm, modname, instance]
foreach ($spec['resources'] as $r) {
    $m = add_module($course, 'page', $r['name'], 'R-' . $r['key'], ['content' => '<p>' . s($r['name']) . '</p>',
        'contentformat' => FORMAT_HTML, 'display' => 0, 'printintro' => 0, 'printlastmodified' => 0]);
    $sites[$r['key']] = [$m->coursemodule, 'page', $m->instance];
}
foreach ($spec['items'] as $it) {
    $due = $at($it['due_day'], 23 * HOURSECS);
    if ($it['type'] === 'assign') {
        $m = add_module($course, 'assign', $it['name'], 'I-' . $it['key'], [
            'assignsubmission_onlinetext_enabled' => ($it['online'] ?? true) ? 1 : 0, 'assignsubmission_file_enabled' => 0,
            'submissiondrafts' => 0, 'requiresubmissionstatement' => 0, 'gradepass' => $it['gradepass'] ?? 0,
            'sendnotifications' => 0, 'sendlatenotifications' => 0, 'sendstudentnotifications' => 0,
            'allowsubmissionsfromdate' => 0, 'duedate' => $due, 'cutoffdate' => 0, 'gradingduedate' => 0,
            'grade' => $it['grademax'], 'teamsubmission' => 0, 'requireallteammemberssubmit' => 0,
            'markingworkflow' => 0, 'markingallocation' => 0, 'blindmarking' => 0,
            'attemptreopenmethod' => 'none', 'maxattempts' => -1]);
    } else if ($it['type'] === 'quiz') {
        $m = add_module($course, 'quiz', $it['name'], 'I-' . $it['key'], [
            'timeopen' => 0, 'timeclose' => $due, 'timelimit' => 0, 'quizpassword' => '', 'overduehandling' => 'autosubmit',
            'graceperiod' => 0, 'preferredbehaviour' => 'deferredfeedback', 'attempts' => 0, 'grademethod' => 1,
            'decimalpoints' => 2, 'questiondecimalpoints' => -1, 'reviewattempt' => 69904, 'reviewcorrectness' => 4368,
            'reviewmarks' => 4368, 'reviewspecificfeedback' => 4368, 'reviewgeneralfeedback' => 4368,
            'reviewrightanswer' => 4368, 'reviewoverallfeedback' => 4368, 'questionsperpage' => 1, 'navmethod' => 'free',
            'shuffleanswers' => 1, 'sumgrades' => 0, 'grade' => $it['grademax'], 'gradepass' => $it['gradepass'] ?? 0]);
    } else {
        throw new coding_exception("tipo de evaluación no soportado: {$it['type']}");
    }
    $sites[$it['key']] = [$m->coursemodule, $it['type'], $m->instance, $it['online'] ?? true];
}

// Entregas y notas (con sus fechas históricas)
foreach ($spec['grades'] as $g) {
    [$cmid, $modname, $instance, $online] = $sites[$g['item']];
    $userid = $users[$g['username']]->id;
    $submitted = $g['submitted_day'] === null ? null : $at($g['submitted_day'], 12 * HOURSECS);
    $graded = $g['graded_day'] === null ? null : $at($g['graded_day'], 14 * HOURSECS);
    if ($modname === 'assign' && $submitted !== null && $online) {
        $DB->insert_record('assign_submission', (object)['assignment' => $instance, 'userid' => $userid,
            'timecreated' => $submitted, 'timemodified' => $submitted, 'timestarted' => null, 'status' => 'submitted',
            'groupid' => 0, 'attemptnumber' => 0, 'latest' => 1]);
    }
    if ($g['raw'] === null) {
        continue;
    }
    $graded = $graded ?? ($submitted ?? $start);
    if ($modname === 'assign') {
        $DB->insert_record('assign_grades', (object)['assignment' => $instance, 'userid' => $userid,
            'timecreated' => $graded, 'timemodified' => $graded, 'grader' => $teacher->id,
            'grade' => $g['raw'], 'attemptnumber' => 0]);
    }
    grade_update('mod/' . $modname, $course->id, 'mod', $modname, $instance, 0,
        ['userid' => $userid, 'rawgrade' => $g['raw'], 'dategraded' => $graded, 'datesubmitted' => $submitted]);
}
// grade_update marca las fechas con «ahora»: se ponen las históricas
foreach ($spec['grades'] as $g) {
    if ($g['raw'] === null) {
        continue;
    }
    [$cmid, $modname, $instance, $online] = $sites[$g['item']];
    $item = grade_item::fetch(['courseid' => $course->id, 'itemtype' => 'mod', 'itemmodule' => $modname,
        'iteminstance' => $instance, 'itemnumber' => 0]);
    $submitted = $g['submitted_day'] === null ? null : $at($g['submitted_day'], 12 * HOURSECS);
    $graded = $g['graded_day'] === null ? ($submitted ?? $start) : $at($g['graded_day'], 14 * HOURSECS);
    $DB->set_field('grade_grades', 'timemodified', $graded, ['itemid' => $item->id, 'userid' => $users[$g['username']]->id]);
    $DB->set_field('grade_grades', 'timecreated', $submitted, ['itemid' => $item->id, 'userid' => $users[$g['username']]->id]);
}

// Registro de actividad: un evento «visto» por cada evento de la especificación
$coursecontext = context_course::instance($course->id);
$rows = [];
$flush = function () use (&$rows, $DB) {
    if ($rows) {
        $DB->insert_records('logstore_standard_log', $rows);
        $rows = [];
    }
};
foreach ($spec['activity'] as $a) {
    $userid = $users[$a['username']]->id;
    if ($a['site'] === null) {
        $base = ['eventname' => '\\core\\event\\course_viewed', 'component' => 'core', 'target' => 'course',
            'objecttable' => null, 'objectid' => null, 'contextid' => $coursecontext->id,
            'contextlevel' => CONTEXT_COURSE, 'contextinstanceid' => $course->id];
    } else {
        [$cmid, $modname, $instance] = $sites[$a['site']];
        $base = ['eventname' => "\\mod_{$modname}\\event\\course_module_viewed", 'component' => "mod_{$modname}",
            'target' => 'course_module', 'objecttable' => $modname, 'objectid' => $instance,
            'contextid' => context_module::instance($cmid)->id, 'contextlevel' => CONTEXT_MODULE,
            'contextinstanceid' => $cmid];
    }
    for ($k = 0; $k < (int)$a['events']; $k++) {
        $rows[] = $base + ['action' => 'viewed', 'crud' => 'r', 'edulevel' => \core\event\base::LEVEL_PARTICIPATING,
            'userid' => $userid, 'courseid' => $course->id, 'relateduserid' => null, 'anonymous' => 0,
            'other' => 'null', 'timecreated' => $at($a['day'], 8 * HOURSECS + ($k % 900) * 60), 'origin' => 'web',
            'ip' => '127.0.0.1', 'realuserid' => null];
        if (count($rows) >= 5000) {
            $flush();
        }
    }
}
$flush();

// Bajas
$manual = enrol_get_plugin('manual');
$instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
foreach ($spec['students'] as $s) {
    if (!empty($s['withdrawn'])) {
        $manual->unenrol_user($instance, $users[$s['username']]->id);
    }
}
rebuild_course_cache($course->id, true);

echo json_encode(['courseid' => (int)$course->id, 'startdate' => $start,
    'sites' => array_map(fn($v) => $v[0], $sites),
    'users' => array_map(fn($u) => (int)$u->id, $users)], JSON_UNESCAPED_UNICODE) . PHP_EOL;
