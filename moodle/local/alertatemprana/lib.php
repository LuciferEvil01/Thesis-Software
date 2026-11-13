<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Enlace «Alerta temprana» en la navegación del curso, para quien puede ver el informe.
 */
function local_alertatemprana_extend_navigation_course(navigation_node $navigation, stdClass $course, context $context) {
    if (has_capability('local/alertatemprana:view', $context)) {
        $url = new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id]);
        $navigation->add(get_string('report', 'local_alertatemprana'), $url, navigation_node::TYPE_SETTING,
            null, 'local_alertatemprana', new pix_icon('i/report', ''));
    }
}

/**
 * Datos de una predicción listos para mostrar.
 */
function local_alertatemprana_calculations(stdClass $prediction): array {
    $c = json_decode($prediction->calculations ?? '', true);
    return is_array($c) ? $c : [];
}

/** Número con coma decimal. */
function local_alertatemprana_num($value, int $decimals = 1): string {
    return $value === null ? '–' : format_float((float)$value, $decimals);
}

/** Escala en que se muestran las notas de una predicción (P16): « (2 a 5)», « (sobre 20)»… */
function local_alertatemprana_scale(?array $scale): string {
    $type = $scale['tipo'] ?? '0-100';
    if ($type === '2-5') {
        return get_string('scale_25', 'local_alertatemprana');
    } else if ($type === 'puntos') {
        return get_string('scale_points', 'local_alertatemprana', local_alertatemprana_num($scale['max'], 0));
    } else if ($type === 'porcentaje') {
        return get_string('scale_pct', 'local_alertatemprana');
    }
    return get_string('scale_100', 'local_alertatemprana');
}

/** Nota en la escala del curso: un decimal en la escala 2–5 y en puntos. */
function local_alertatemprana_grade($value): string {
    return local_alertatemprana_num($value, 1);
}

/** Nombre de la evaluación de referencia de una publicación. */
function local_alertatemprana_anchor_name(stdClass $run): string {
    if (empty($run->anchorcmid)) {
        return '–';
    }
    $modinfo = get_fast_modinfo($run->courseid);
    $cm = $modinfo->cms[$run->anchorcmid] ?? null;
    return $cm ? format_string($cm->name, true, ['context' => context_module::instance($cm->id)]) : '–';
}

/** Motivo de una publicación, para mostrarlo. */
function local_alertatemprana_reason(stdClass $run): string {
    $key = ($run->reason ?? 'notas') === 'profesor' ? 'reason_teacher' : 'reason_grades';
    return get_string($key, 'local_alertatemprana');
}
