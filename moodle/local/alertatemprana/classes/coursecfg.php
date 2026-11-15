<?php
namespace local_alertatemprana;

/**
 * Evaluaciones que el sistema analiza en cada curso (P20, P21).
 *
 * Las tareas (`assign`) entran siempre: son las que disparan la predicción automática y equivalen a
 * las TMA con que se entrenó el modelo. El profesor decide si entran también los cuestionarios
 * (`quiz`), la evaluación de calificación automática que equivale a las CMA; entonces cuentan en la
 * nota media y la predicción que él pide toma como referencia la evaluación más reciente con notas de
 * cualquiera de los dos tipos. Los demás tipos de evaluación de Moodle no se analizan: su nota no es
 * comparable con la de una tarea.
 *
 * Requisito de la escala (P21): una tarea solo entra si se califica de 2 a 5, como puntuación (mínimo
 * 0 o 2, máximo 5) o con una escala de Moodle de cuatro elementos (numéricos 2, 3, 4 y 5, o palabras
 * ordenadas de menor a mayor, como Mal, Regular, Bien y Excelente). Es la misma regla que aplica el
 * módulo de predicción (`alerta.calificacion.tarea_en_escala`).
 */
class coursecfg {
    const ALWAYS = 'assign';
    const QUIZ = 'quiz';

    /** @return string[] tipos que se analizan en el curso, con `assign` siempre */
    public static function types(int $courseid): array {
        return self::quizzes($courseid) ? [self::ALWAYS, self::QUIZ] : [self::ALWAYS];
    }

    /** ¿Entran los cuestionarios del curso? */
    public static function quizzes(int $courseid): bool {
        global $DB;
        $saved = (string)$DB->get_field('local_alertatemprana_cfg', 'types', ['courseid' => $courseid]);
        return in_array(self::QUIZ, explode(',', $saved), true);
    }

    public static function set_quizzes(int $courseid, bool $include): void {
        global $DB;
        $types = $include ? self::ALWAYS . ',' . self::QUIZ : self::ALWAYS;
        $record = $DB->get_record('local_alertatemprana_cfg', ['courseid' => $courseid]);
        $data = ['courseid' => $courseid, 'types' => $types, 'timemodified' => time()];
        if ($record) {
            $DB->update_record('local_alertatemprana_cfg', (object)(['id' => $record->id] + $data));
        } else {
            $DB->insert_record('local_alertatemprana_cfg', (object)$data);
        }
    }

    /** Valores de los elementos de una escala de Moodle, o null si no es la escala de 2 a 5 en ningún sentido. */
    public static function scale_values(string $scale): ?array {
        $items = array_map('trim', explode(',', $scale));
        if (count(array_filter($items, 'is_numeric')) === count($items)) {
            return array_map('floatval', $items);
        }
        return count($items) === 4 ? [2.0, 3.0, 4.0, 5.0] : null;
    }

    /** ¿Se califica de 2 a 5 un ítem de tarea del libro de calificaciones? */
    public static function graded_two_to_five(\stdClass $item): bool {
        if ((int)$item->gradetype === 2) {
            $values = self::scale_values((string)($item->scale ?? ''));
            return $values !== null && min($values) == 2 && max($values) == 5;
        }
        return (int)$item->gradetype === 1 && (float)$item->grademax == 5 && in_array((float)$item->grademin, [0.0, 2.0]);
    }

    /** @return string[] nombres de las tareas del curso que no se califican de 2 a 5 y no entran */
    public static function out_of_scale(int $courseid): array {
        global $DB;
        $sql = "SELECT gi.id, gi.itemname, gi.gradetype, gi.grademin, gi.grademax, s.scale
                  FROM {grade_items} gi
             LEFT JOIN {scale} s ON s.id = gi.scaleid
                 WHERE gi.courseid = :courseid AND gi.itemtype = 'mod' AND gi.itemmodule = 'assign'
                       AND gi.itemnumber = 0 AND gi.gradetype IN (1, 2)
              ORDER BY gi.sortorder";
        $out = [];
        foreach ($DB->get_records_sql($sql, ['courseid' => $courseid]) as $item) {
            if (!self::graded_two_to_five($item)) {
                $out[] = format_string($item->itemname);
            }
        }
        return $out;
    }
}
