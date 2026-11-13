<?php
defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Alerta temprana';
$string['report'] = 'Alerta temprana';
$string['alertatemprana:view'] = 'Ver el informe de alerta temprana y actuar sobre las alertas';
$string['alertatemprana:submit'] = 'Publicar predicciones de alerta temprana';
$string['messageprovider:alerta'] = 'Estudiantes en riesgo académico detectados por la alerta temprana';

$string['cut_first'] = 'Primer corte';
$string['cut_mid'] = 'Segundo corte';
$string['cut_last'] = 'Tercer corte';

$string['notification_subject'] = 'Estudiantes en riesgo académico en {$a->course} (notas de {$a->evaluation})';
$string['notification_body'] = 'Hola, {$a->firstname}:

La alerta temprana ha detectado {$a->flagged} de {$a->total} estudiantes en riesgo académico en {$a->course}, ahora que están las notas de {$a->evaluation}.

Puede revisar la lista y actuar sobre cada alerta en: {$a->url}';
$string['notification_html'] = '<p>Hola, {$a->firstname}:</p><p>La alerta temprana ha detectado <strong>{$a->flagged} de {$a->total}</strong> estudiantes en riesgo académico en <strong>{$a->course}</strong>, ahora que están las notas de {$a->evaluation}.</p><p><a href="{$a->url}">Revisar la lista y actuar sobre cada alerta</a></p>';

$string['noruns'] = 'Todavía no hay predicciones para este curso. Se calculan solas cuando una tarea queda calificada (todas sus entregas con nota) y también cuando usted las pide con el botón, siempre que la evaluación más reciente con notas tenga al menos el 90 % de ellas.';
$string['runsummary'] = '<strong>{$a->flagged} de {$a->total}</strong> estudiantes en riesgo académico con los datos hasta el día {$a->day} del curso ({$a->date}), tomando como referencia las notas de <em>{$a->evaluation}</em> ({$a->reason}). Modelo {$a->model}; se marca en riesgo académico a quien tiene una probabilidad de riesgo académico mayor que el {$a->threshold} %.';
$string['runheading'] = 'Predicción del {$a}';
$string['history'] = 'Predicciones publicadas';
$string['reason'] = 'Motivo';
$string['reason_grades'] = 'notas completas';
$string['reason_teacher'] = 'pedida por el profesor';
$string['anchor'] = 'Evaluación de referencia';
$string['flaggedcol'] = 'En riesgo académico';
$string['requestnow'] = 'Calcular predicciones ahora';
$string['requesthelp'] = 'Usa las notas publicadas hasta hoy y la actividad de los estudiantes. Tarda unos minutos.';
$string['requestqueued'] = 'Solicitud registrada. La predicción aparecerá en este informe en unos minutos.';
$string['requestpending'] = 'Hay una solicitud de predicción en curso (desde {$a}). El informe se actualizará en unos minutos.';
$string['runhelp'] = 'El umbral es la proporción de estudiantes en riesgo académico que había en este punto del curso en los cursos con que se ajustó el modelo, así que la lista incluye también a algunos estudiantes que aprobarán: está ordenada por probabilidad para que empiece por los de mayor riesgo. Puede aceptar cada alerta, marcarla como no aplicable o como incorrecta; esas respuestas quedan registradas.';
$string['showall'] = 'Mostrar todos los estudiantes';
$string['showflagged'] = 'Mostrar solo los estudiantes en riesgo académico';
$string['noflagged'] = 'Ningún estudiante en riesgo académico en esta predicción.';
$string['student'] = 'Estudiante';
$string['probability'] = 'Probabilidad de riesgo académico';
$string['meangrade'] = 'Nota media';
$string['lastgrade'] = 'Última evaluación';
$string['scale_25'] = ' (2 a 5)';
$string['scale_points'] = ' (sobre {$a})';
$string['scale_pct'] = ' (% de la máxima)';
$string['scale_100'] = ' (0 a 100)';
$string['recentactivity'] = 'Actividad (4 semanas)';
$string['submissions'] = 'Entregas';
$string['status'] = 'Estado';
$string['actions'] = 'Acciones';
$string['atrisk'] = 'En riesgo académico';
$string['pending'] = 'Sin revisar';
$string['percentileshort'] = 'percentil {$a}';
$string['messageselected'] = 'Enviar un mensaje a los seleccionados';
$string['messageto'] = 'Para: {$a}';
$string['messagessent'] = 'Mensaje enviado a {$a} estudiantes.';
$string['noneselected'] = 'No ha seleccionado ningún estudiante.';
$string['actionsaved'] = 'Acción registrada.';

$string['action_fixed'] = 'Aceptar';
$string['action_notapplicable'] = 'No aplicable';
$string['action_incorrectlyflagged'] = 'Marcado incorrectamente';
$string['action_useful'] = 'Útil';
$string['action_notuseful'] = 'No útil';
$string['action_predictiondetails'] = 'Ver detalles';
$string['action_sendmessage'] = 'Enviar mensaje';

$string['details'] = 'Detalles de la predicción';
$string['detailsatrisk'] = 'Probabilidad de riesgo académico: <strong>{$a->prob} %</strong> (se marca en riesgo académico cuando supera el {$a->threshold} %).';
$string['detailsnotatrisk'] = 'Probabilidad de riesgo académico: <strong>{$a->prob} %</strong>, no supera el umbral ({$a->threshold} %).';
$string['detailshelp'] = 'Las notas están en la escala del curso: una evaluación no entregada cuenta como la nota más baja y una entregada que aún no tiene nota no cuenta. Los percentiles comparan al estudiante con sus compañeros del curso: 0 es el más bajo y 100 el más alto. El efecto indica si el valor de la variable aumenta o reduce la probabilidad de riesgo académico respecto a la del estudiante promedio del curso.';
$string['variable'] = 'Variable';
$string['value'] = 'Valor';
$string['effect'] = 'Efecto';
$string['raisesrisk'] = 'Aumenta la probabilidad';
$string['lowersrisk'] = 'Reduce la probabilidad';
$string['neutral'] = 'Neutro';
$string['var_mean_score_with_zeros_raw'] = 'Nota media de las evaluaciones hasta la de referencia';
$string['var_mean_score_with_zeros_pct'] = 'Posición de la nota media en el curso';
$string['var_last_score_raw'] = 'Nota de la evaluación de referencia';
$string['var_last_score_pct'] = 'Posición de la nota de la última evaluación en el curso';
$string['var_recent_clicks_28d_pct'] = 'Actividad en Moodle en las últimas 4 semanas, frente al curso';
$string['var_submission_rate'] = 'Proporción de evaluaciones entregadas a tiempo';

$string['privacy:metadata:local_alertatemprana_pred'] = 'Predicción de cada estudiante en cada publicación: probabilidad de riesgo académico y alerta.';
$string['privacy:metadata:local_alertatemprana_pred:userid'] = 'Estudiante al que se refiere la predicción.';
$string['privacy:metadata:local_alertatemprana_pred:predictionscore'] = 'Probabilidad estimada de riesgo académico.';
$string['privacy:metadata:local_alertatemprana_pred:calculations'] = 'Variables del estudiante usadas en la predicción.';
$string['privacy:metadata:local_alertatemprana_act'] = 'Acciones de los profesores sobre las predicciones.';
$string['privacy:metadata:local_alertatemprana_act:userid'] = 'Profesor que realizó la acción.';
$string['privacy:metadata:local_alertatemprana_act:actionname'] = 'Acción realizada.';
$string['privacy:metadata:local_alertatemprana_req'] = 'Solicitudes de predicción hechas por los profesores.';
$string['privacy:metadata:local_alertatemprana_req:userid'] = 'Profesor que pidió la predicción.';
$string['privacy:metadata:logstore'] = 'El plugin agrega el registro estándar de Moodle para medir la actividad de los estudiantes.';
$string['settings'] = 'Evaluaciones que se analizan';
$string['settingsintro'] = 'Las tareas entran siempre: cuando todas las entregas de una tarea tienen nota, el sistema calcula una predicción nueva y le avisa. Puede añadir otros tipos de evaluación de su curso. Entonces entran también en la nota media de cada estudiante y, cuando usted pide una predicción con el botón, se toma como referencia la evaluación más reciente con notas, sea del tipo que sea.';
$string['settingsadvice'] = 'Incluya solo las evaluaciones que cuentan para la nota final de la asignatura. Con los datos de entrenamiento, los cuestionarios que contaban para la nota mejoraron la predicción y los de práctica, que apenas pesaban, la empeoraron.';
$string['settingstype'] = 'Tipo de evaluación';
$string['settingscount'] = 'Actividades calificables en el curso';
$string['settingsalways'] = 'Siempre: disparan la predicción automática.';
$string['settingsnodate'] = 'No puede elegirse: el sistema no sabe leer su fecha de cierre.';
$string['settingssaved'] = 'Evaluaciones guardadas. Se aplican desde la próxima predicción.';
$string['settingscurrent'] = 'Evaluaciones que se analizan: {$a}.';
$string['settingschange'] = 'Cambiar';
