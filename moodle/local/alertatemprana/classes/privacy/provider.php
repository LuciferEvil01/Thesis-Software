<?php
namespace local_alertatemprana\privacy;

use core_privacy\local\metadata\collection;

/**
 * Datos personales que guarda el plugin. La exportación y el borrado a petición del usuario
 * quedan para una versión posterior.
 */
class provider implements \core_privacy\local\metadata\provider {
    public static function get_metadata(collection $collection): collection {
        $collection->add_database_table('local_alertatemprana_pred', [
            'userid' => 'privacy:metadata:local_alertatemprana_pred:userid',
            'predictionscore' => 'privacy:metadata:local_alertatemprana_pred:predictionscore',
            'calculations' => 'privacy:metadata:local_alertatemprana_pred:calculations',
        ], 'privacy:metadata:local_alertatemprana_pred');
        $collection->add_database_table('local_alertatemprana_act', [
            'userid' => 'privacy:metadata:local_alertatemprana_act:userid',
            'actionname' => 'privacy:metadata:local_alertatemprana_act:actionname',
        ], 'privacy:metadata:local_alertatemprana_act');
        $collection->add_database_table('local_alertatemprana_req', [
            'userid' => 'privacy:metadata:local_alertatemprana_req:userid',
        ], 'privacy:metadata:local_alertatemprana_req');
        $collection->add_subsystem_link('core_logstore', [], 'privacy:metadata:logstore');
        return $collection;
    }
}
