<?php
// Sistema de alerta temprana de estudiantes en riesgo académico (tesis, MatCom, Universidad de La Habana).
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_alertatemprana';
$plugin->version = 2026111401;
$plugin->requires = 2025041400; // Moodle 5.0.
$plugin->maturity = MATURITY_ALPHA;
$plugin->release = '0.8 (P21: tareas de 2 a 5; P22: panel del informe y aviso en el curso)';
