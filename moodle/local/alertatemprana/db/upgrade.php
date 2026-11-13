<?php
defined('MOODLE_INTERNAL') || die();

function xmldb_local_alertatemprana_upgrade($oldversion) {
    global $DB;
    $dbman = $DB->get_manager();
    if ($oldversion < 2026102400) {
        // F6: tablas de publicaciones, predicciones y acciones
        if (!$dbman->table_exists('local_alertatemprana_run')) {
            $dbman->install_from_xmldb_file(__DIR__ . '/install.xml');
        }
        upgrade_plugin_savepoint(true, 2026102400, 'local', 'alertatemprana');
    }
    if ($oldversion < 2026102401) {
        // Datos de cursos borrados antes de que existiera el observador
        $orphans = $DB->get_fieldset_sql('SELECT DISTINCT r.courseid FROM {local_alertatemprana_run} r
                                         LEFT JOIN {course} c ON c.id = r.courseid WHERE c.id IS NULL');
        foreach ($orphans as $courseid) {
            \local_alertatemprana\observer::delete_course_data((int)$courseid);
        }
        upgrade_plugin_savepoint(true, 2026102401, 'local', 'alertatemprana');
    }
    if ($oldversion < 2026102800) {
        // P12: varias publicaciones por curso, con su motivo, y cola de solicitudes
        $run = new xmldb_table('local_alertatemprana_run');
        $old = new xmldb_index('coursecut', XMLDB_INDEX_UNIQUE, ['courseid', 'cut']);
        if ($dbman->index_exists($run, $old)) {
            $dbman->drop_index($run, $old);
        }
        $index = new xmldb_index('coursetime', XMLDB_INDEX_NOTUNIQUE, ['courseid', 'timecreated']);
        if (!$dbman->index_exists($run, $index)) {
            $dbman->add_index($run, $index);
        }
        $fields = [new xmldb_field('reason', XMLDB_TYPE_CHAR, '20', null, XMLDB_NOTNULL, null, 'notas', 'cut'),
            new xmldb_field('requestedby', XMLDB_TYPE_INTEGER, '10', null, null, null, null, 'reason')];
        foreach ($fields as $field) {
            if (!$dbman->field_exists($run, $field)) {
                $dbman->add_field($run, $field);
            }
        }
        if (!$dbman->table_exists('local_alertatemprana_req')) {
            $dbman->install_one_table_from_xmldb_file(__DIR__ . '/install.xml', 'local_alertatemprana_req');
        }
        upgrade_plugin_savepoint(true, 2026102800, 'local', 'alertatemprana');
    }
    if ($oldversion < 2026110501) {
        // P20: tipos de evaluación elegidos por el profesor en cada curso
        if (!$dbman->table_exists('local_alertatemprana_cfg')) {
            $dbman->install_one_table_from_xmldb_file(__DIR__ . '/install.xml', 'local_alertatemprana_cfg');
        }
        upgrade_plugin_savepoint(true, 2026110501, 'local', 'alertatemprana');
    }
    return true;
}
