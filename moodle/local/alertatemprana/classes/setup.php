<?php
namespace local_alertatemprana;

/**
 * Configura el acceso del sistema de alerta temprana a este Moodle (idempotente). Sirve igual en el
 * laboratorio que en una instalación real (EVEA):
 *
 * - usuario de servicio `alerta_servicio`, que a nivel de sitio solo puede usar REST (rol
 *   `alerta_servicio`); cada profesor lo matricula en su curso como profesor sin permiso de edición;
 * - servicio externo `alerta_connector` con las funciones que usa el sistema;
 * - token permanente del usuario para ese servicio.
 *
 * Requiere los servicios web y el protocolo REST activados (lo hace también este método).
 */
class setup {
    const USERNAME = 'alerta_servicio';
    const SERVICE = 'alerta_connector';
    const FUNCTIONS = [
        'core_webservice_get_site_info',
        'core_course_get_courses', 'core_course_get_courses_by_field', 'core_course_get_contents',
        'core_course_get_categories', 'core_enrol_get_users_courses', 'core_enrol_get_enrolled_users',
        'mod_assign_get_assignments', 'mod_assign_get_submissions', 'mod_assign_get_grades',
        'mod_quiz_get_quizzes_by_courses', 'gradereport_user_get_grade_items',
        'local_alertatemprana_get_activity', 'local_alertatemprana_get_gradeitems', 'local_alertatemprana_get_course_config',
        'local_alertatemprana_save_predictions',
        'local_alertatemprana_get_runs', 'local_alertatemprana_get_actions',
        'local_alertatemprana_get_requests', 'local_alertatemprana_complete_requests',
    ];

    /**
     * @param string|null $password contraseña del usuario de servicio si hay que crearlo (si no, una aleatoria)
     * @return array usuario, servicio, número de funciones y token
     */
    public static function run(?string $password = null): array {
        global $CFG, $DB;
        require_once($CFG->dirroot . '/user/lib.php');
        require_once($CFG->libdir . '/externallib.php');
        require_once($CFG->dirroot . '/webservice/lib.php');

        set_config('enablewebservices', 1);
        $protocols = array_filter(explode(',', get_config('core', 'webserviceprotocols') ?: ''));
        if (!in_array('rest', $protocols)) {
            set_config('webserviceprotocols', implode(',', array_merge($protocols, ['rest'])));
        }

        $user = $DB->get_record('user', ['username' => self::USERNAME, 'mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0]);
        if (!$user) {
            $id = user_create_user((object)[
                'auth' => 'manual', 'confirmed' => 1, 'mnethostid' => $CFG->mnet_localhost_id,
                'username' => self::USERNAME, 'password' => $password ?: generate_password(20),
                'firstname' => 'Servicio', 'lastname' => 'Alerta temprana',
                'email' => self::USERNAME . '@' . (parse_url($CFG->wwwroot, PHP_URL_HOST) ?: 'localhost'),
            ], true, false);
            $user = $DB->get_record('user', ['id' => $id], '*', MUST_EXIST);
        }

        $system = \context_system::instance();
        $role = $DB->get_record('role', ['shortname' => 'alerta_servicio']);
        if (!$role) {
            $roleid = create_role('Servicio de alerta temprana', 'alerta_servicio',
                'Solo permite usar el protocolo REST; cada curso le da acceso al matricularlo como profesor.');
            $role = $DB->get_record('role', ['id' => $roleid], '*', MUST_EXIST);
        }
        set_role_contextlevels($role->id, [CONTEXT_SYSTEM]);
        $DB->delete_records_select('role_capabilities', 'roleid = ? AND contextid = ? AND capability <> ?',
            [$role->id, $system->id, 'webservice/rest:use']);
        assign_capability('webservice/rest:use', CAP_ALLOW, $role->id, $system->id, true);
        $system->mark_dirty();
        if (!user_has_role_assignment($user->id, $role->id, $system->id)) {
            role_assign($role->id, $user->id, $system->id);
        }

        $service = $DB->get_record('external_services', ['shortname' => self::SERVICE]);
        if (!$service) {
            $service = (object)['name' => 'Alerta temprana (conector)', 'shortname' => self::SERVICE, 'enabled' => 1,
                'restrictedusers' => 1, 'downloadfiles' => 0, 'uploadfiles' => 0,
                'timecreated' => time(), 'timemodified' => time()];
            $service->id = $DB->insert_record('external_services', $service);
        }
        $added = 0;
        foreach (self::FUNCTIONS as $function) {
            if (!$DB->record_exists('external_functions', ['name' => $function])) {
                continue;
            }
            $key = ['externalserviceid' => $service->id, 'functionname' => $function];
            if (!$DB->record_exists('external_services_functions', $key)) {
                $DB->insert_record('external_services_functions', (object)$key);
            }
            $added++;
        }
        $allowed = ['externalserviceid' => $service->id, 'userid' => $user->id];
        if (!$DB->record_exists('external_services_users', $allowed)) {
            $DB->insert_record('external_services_users', (object)($allowed + ['timecreated' => time()]));
        }
        $tokenkey = $allowed + ['tokentype' => EXTERNAL_TOKEN_PERMANENT];
        if (!$token = $DB->get_record('external_tokens', $tokenkey)) {
            \core_external\util::generate_token(EXTERNAL_TOKEN_PERMANENT, \core_external\util::get_service_by_id($service->id),
                $user->id, $system);
            $token = $DB->get_record('external_tokens', $tokenkey, '*', MUST_EXIST);
        }
        return ['usuario' => $user->username, 'userid' => (int)$user->id, 'servicio' => $service->shortname,
            'funciones' => $added, 'url' => rtrim($CFG->wwwroot, '/'), 'token' => $token->token];
    }
}
