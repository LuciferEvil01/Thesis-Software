<?php
defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Early warning';
$string['report'] = 'Early warning';
$string['alertatemprana:view'] = 'View the early warning report and act on alerts';
$string['alertatemprana:submit'] = 'Publish early warning predictions';
$string['messageprovider:alerta'] = 'Students at academic risk detected by the early warning system';

$string['cut_first'] = 'First cut';
$string['cut_mid'] = 'Second cut';
$string['cut_last'] = 'Third cut';

$string['notification_subject'] = 'Students at academic risk in {$a->course} (grades of {$a->evaluation})';
$string['notification_body'] = 'Hi {$a->firstname},

The early warning system has identified {$a->flagged} of {$a->total} students at academic risk in {$a->course}, now that the grades of {$a->evaluation} are in.

Review the list and act on each alert at: {$a->url}';
$string['notification_html'] = '<p>Hi {$a->firstname},</p><p>The early warning system has identified <strong>{$a->flagged} of {$a->total}</strong> students at academic risk in <strong>{$a->course}</strong>, now that the grades of {$a->evaluation} are in.</p><p><a href="{$a->url}">Review the list and act on each alert</a></p>';

$string['noruns'] = 'There are no predictions for this course yet. They are computed automatically when an assignment is fully graded (every submission has a grade) and whenever you request them with the button, as long as the most recent assessment with grades has at least 90 % of them.';
$string['runsummary'] = '<strong>{$a->flagged} of {$a->total}</strong> students at academic risk using data up to day {$a->day} of the course ({$a->date}), with the grades of <em>{$a->evaluation}</em> as reference ({$a->reason}). Model {$a->model}; students whose probability of academic risk exceeds {$a->threshold} % are flagged at academic risk.';
$string['runheading'] = 'Prediction of {$a}';
$string['history'] = 'Published predictions';
$string['reason'] = 'Reason';
$string['reason_grades'] = 'grades complete';
$string['reason_teacher'] = 'requested by the teacher';
$string['anchor'] = 'Reference assessment';
$string['flaggedcol'] = 'At academic risk';
$string['requestnow'] = 'Compute predictions now';
$string['requesthelp'] = 'Uses the grades published so far and student activity. Takes a few minutes.';
$string['requestqueued'] = 'Request recorded. The prediction will appear in this report in a few minutes.';
$string['requestpending'] = 'A prediction request is in progress (since {$a}). The report will update in a few minutes.';
$string['runhelp'] = 'The threshold is the proportion of students at academic risk at this point of the course in the courses the model was fitted on, so the list also includes some students who will pass: it is sorted by probability so that you can start with those at highest risk. You can accept each alert, mark it as not applicable or as incorrect; your answers are recorded.';
$string['showall'] = 'Show all students';
$string['showflagged'] = 'Show only students at academic risk';
$string['noflagged'] = 'No students at academic risk in this prediction.';
$string['student'] = 'Student';
$string['probability'] = 'Probability of academic risk';
$string['meangrade'] = 'Mean grade';
$string['lastgrade'] = 'Last assessment';
$string['scale_25'] = ' (2 to 5)';
$string['scale_points'] = ' (out of {$a})';
$string['scale_pct'] = ' (% of maximum)';
$string['scale_100'] = ' (0 to 100)';
$string['recentactivity'] = 'Activity (4 weeks)';
$string['submissions'] = 'Submissions';
$string['status'] = 'Status';
$string['actions'] = 'Actions';
$string['atrisk'] = 'At academic risk';
$string['pending'] = 'Not reviewed';
$string['percentileshort'] = 'percentile {$a}';
$string['messageselected'] = 'Send a message to the selected students';
$string['messageto'] = 'To: {$a}';
$string['messagessent'] = 'Message sent to {$a} students.';
$string['noneselected'] = 'No students selected.';
$string['actionsaved'] = 'Action recorded.';

$string['action_fixed'] = 'Accept';
$string['action_notapplicable'] = 'Not applicable';
$string['action_incorrectlyflagged'] = 'Incorrectly flagged';
$string['action_useful'] = 'Useful';
$string['action_notuseful'] = 'Not useful';
$string['action_predictiondetails'] = 'View details';
$string['action_sendmessage'] = 'Send message';

$string['details'] = 'Prediction details';
$string['detailsatrisk'] = 'Probability of academic risk: <strong>{$a->prob} %</strong> (flagged at academic risk when it exceeds {$a->threshold} %).';
$string['detailsnotatrisk'] = 'Probability of academic risk: <strong>{$a->prob} %</strong>, does not exceed the threshold ({$a->threshold} %).';
$string['detailshelp'] = 'Grades are on the course scale: a missing assessment counts as the lowest grade and a submission not graded yet does not count. Percentiles compare the student with their classmates: 0 is the lowest and 100 the highest. The effect shows whether the value raises or lowers the probability of academic risk with respect to the average student of the course.';
$string['variable'] = 'Variable';
$string['value'] = 'Value';
$string['effect'] = 'Effect';
$string['raisesrisk'] = 'Raises the probability';
$string['lowersrisk'] = 'Lowers the probability';
$string['neutral'] = 'Neutral';
$string['var_mean_score_with_zeros_raw'] = 'Mean assessment grade up to the reference one';
$string['var_mean_score_with_zeros_pct'] = 'Position of the mean grade in the course';
$string['var_last_score_raw'] = 'Grade of the reference assessment';
$string['var_last_score_pct'] = 'Position of the last assessment grade in the course';
$string['var_recent_clicks_28d_pct'] = 'Moodle activity in the last 4 weeks, compared with the course';
$string['var_submission_rate'] = 'Share of assessments submitted on time';

$string['privacy:metadata:local_alertatemprana_pred'] = 'Prediction for each student in each publication: probability of academic risk and alert.';
$string['privacy:metadata:local_alertatemprana_pred:userid'] = 'Student the prediction refers to.';
$string['privacy:metadata:local_alertatemprana_pred:predictionscore'] = 'Estimated probability of academic risk.';
$string['privacy:metadata:local_alertatemprana_pred:calculations'] = 'Student variables used in the prediction.';
$string['privacy:metadata:local_alertatemprana_act'] = 'Teacher actions on the predictions.';
$string['privacy:metadata:local_alertatemprana_act:userid'] = 'Teacher who performed the action.';
$string['privacy:metadata:local_alertatemprana_act:actionname'] = 'Action performed.';
$string['privacy:metadata:local_alertatemprana_req'] = 'Prediction requests made by teachers.';
$string['privacy:metadata:local_alertatemprana_req:userid'] = 'Teacher who requested the prediction.';
$string['privacy:metadata:logstore'] = 'The plugin aggregates Moodle\'s standard log to measure student activity.';
$string['panel'] = 'Prediction';
$string['quizzes'] = 'Include the course quizzes';
$string['quizzeshelp'] = 'Assignments are always included, and each one triggers the automatic prediction when all its submissions are graded. Quizzes, which Moodle grades automatically, are included only if you turn this option on: they count towards the mean grade and, when you request a prediction, the most recent graded quiz can be used as the reference. Turn it on only if quizzes count towards the final grade.';
$string['quizzeson'] = 'Quizzes are included from the next prediction.';
$string['quizzesoff'] = 'Quizzes are no longer included from the next prediction.';
$string['outofscale'] = 'These assignments are not analysed because they are not graded from 2 to 5 (as points from 2 to 5 or with a four-item scale, such as Poor, Fair, Good and Excellent): {$a}.';
$string['bannerlast'] = 'Latest prediction, with data up to {$a->date} and the assessment "{$a->evaluation}": {$a->flagged} of {$a->total} students at risk.';
$string['bannernone'] = 'No prediction yet: it will be computed when an assignment has all its grades.';
$string['bannerpending'] = 'A prediction is in progress.';
$string['bannerreport'] = 'View report';
