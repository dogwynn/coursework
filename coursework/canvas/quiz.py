'''TODO

'''
import pprint
from pathlib import Path
from typing import Union
import random
import logging
import itertools

from toolz.curried import (
    curry, merge, pipe, assoc, dissoc, itemmap, compose, juxt, complement,
    filter, map,
    do,
)

from larc.common import (
    Null, vcall, no_pyrsistent, remove_keys, update_if_key_exists,
    maybe_pipe,
)
from larc.rest import (
    get_id_resources, IdResourceEndpoint, new_id_resource,
    update_endpoint,
)
from larc import parallel

from .course import (
    Course, course_resource_docstring, course_id_tuple,
    create_course_resource_docstring,
)
from . import assignment
from .metadata import get_metadata, set_metadata
from .. import common
from .. import templates

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

pmap = parallel.pmap('thread')

ANSWER_TYPES = {
    "calculated_question",
    "essay_question",
    "file_upload_question",
    "fill_in_multiple_blanks_question",
    "matching_question",
    "multiple_answers_question",
    "multiple_choice_question",
    "multiple_dropdowns_question",
    "numerical_question",
    "short_answer_question",
    "text_only_question",
    "true_false_question",
}

Quiz = IdResourceEndpoint

quizzes = get_id_resources(
    'quizzes', form_key='quiz', memo=True,
    help=course_resource_docstring('quizzes'),
)

new_quiz = new_id_resource(
    'quizzes', form_key='quiz',
    help=create_course_resource_docstring(
        'quiz', {'title': 'Quiz About Something',
                 'time_limit': 30,
                 'description': '<p>Some HTML content.</p>'}
    ),
)

Question = IdResourceEndpoint

questions = get_id_resources(
    'questions', form_key='question',
    # data={'include[]': ['content_details']},
    help='''For a given quiz endpoint, return a tuple of its question endpoints

    Example:

    >>> course, *_ = coursework.canvas.course.all_courses(api())
    >>> quiz, *_ = coursework.canvas.quiz.quizzes(course)
    >>> questions = coursework.canvas.quiz.questions(quiz)
    '''
)

new_question = new_id_resource(
    'questions', form_key='question',
    help='''For a given quiz endpoint, add a new question.

    Example:

    >>> course, *_ = coursework.canvas.course.all_courses(api())
    >>> quiz, *_ = coursework.canvas.quiz.quizzes(course)
    >>> new_question = coursework.canvas.quiz.new_question(
    ...    quiz, {'question_text': 'Text of question',
    ...           'question_type': 'multiple_choice_question',
    ...           'answers': [{'answer_text': 'Correct answer',
    ...                        'weight': 100},
    ...                       {'answer_text': 'Incorrect answer',
    ...                        'weight': 0}]}
    ... )
    ''',
)

Submission = IdResourceEndpoint

submissions = get_id_resources(
    'submissions', form_key='submission',
    json={'include': ['submission', 'user', 'quiz']},
    unpack_f=lambda s: s['quiz_submissions'],
    single_unpack_f=lambda s: s['quiz_submissions'][0],
    help='''For a given quiz endpoint, return a tuple of its
    submission endpoints

    Example:

    >>> course, *_ = coursework.canvas.course.all_courses(api())
    >>> quiz, *_ = coursework.canvas.course.quizzes(course)
    >>> submissions = coursework.canvas.quiz.submissions(quiz)
    '''
)

def events(submission: Submission):
    '''For a given submission endpoint, return its submission event
    objects

    Example:

    >>> course, *_ = coursework.canvas.course.all_courses(api())
    >>> quiz, *_ = coursework.canvas.course.quizzes(course)
    >>> submission, *_ = coursework.canvas.quiz.submissions(quiz)
    >>> events = coursework.canvas.quiz.events(submission)

    '''
    return submission('events').get().json()['quiz_submission_events']

def pprint_answer(answer: dict):
    return pipe(
        answer,
        no_pyrsistent,
        pprint.pformat,
    )

answer_key_map = {
    'comments': 'answer_comments',
    'match_left': 'answer_match_left',
    'ml': 'answer_match_left',
    'match_right': 'answer_match_right',
    'mr': 'answer_match_right',
    'incorrect': 'matching_answer_incorrect_matches',
    'weight': 'answer_weight',
    'w': 'answer_weight',
    'html': 'answer_html',
    'h': 'answer_html',
    'text': 'answer_text',
    't': 'answer_text',
}

class answer_keys:
    text = 'answer_text'
    html = 'answer_html'
    match_right = 'answer_match_right'
    match_left = 'answer_match_left'
    incorrect = 'matching_answer_incorrect_matches'
    weight = 'answer_weight'

def map_answer_keys(answer: dict):
    return pipe(
        answer,
        itemmap(vcall(lambda k, v: (answer_key_map.get(k, k), v))),
    )

@curry
def render_answer_html(course: Course, course_root: str,
                       answer: dict):
    return pipe(
        answer,
        update_if_key_exists(
            answer_keys.html,
            lambda a: str(templates.common.render_markdown_content(
                course, course_root, str(a[answer_keys.html]),
            )),
        ),
    )

def render_text_content(answer: dict):
    return pipe(
        [answer_keys.text, answer_keys.match_left,
         answer_keys.match_right],
        filter(lambda k: k in answer),
        map(lambda k: {k: str(answer[k])}),
        merge,
        lambda d: merge(answer, d),
    )

def add_weight(answer: dict):
    def is_a_matching_question(answer):
        return pipe(
            [answer_keys.match_left, answer_keys.incorrect],
            map(lambda k: k in answer),
            any,
        )

    needs_weight = compose(
        any, juxt(
            complement(is_a_matching_question),
        ),
    )

    if needs_weight(answer):
        return assoc(answer, answer_keys.weight, int(
            answer.get(answer_keys.weight, 0) and 100
        ))

    return answer

@curry
def process_answer(course: Course, course_root: str, answer: dict):
    answer = map_answer_keys(answer)

    if not ({answer_keys.text, answer_keys.html} & set(answer)):
        log.error(
            'Answer has neither answer_text nor answer_html:\n'
            f'{pprint_answer(answer)}'
        )
        return Null

    return pipe(
        answer,
        render_answer_html(course, course_root),
        render_text_content,
        add_weight,
    )

def pprint_question(question: dict):
    return pipe(
        question,
        no_pyrsistent,
        pprint.pformat,
    )

question_key_map = {
    'text': 'question_text',
    'type': 'question_type',
    'points': 'points_possible',
    'p': 'points_possible',
    'incorrect': 'matching_answer_incorrect_matches',
    'answer': 'answers',
    'a': 'answers',
}

def map_question_keys(question: dict):
    return pipe(
        question,
        itemmap(vcall(lambda k, v: (question_key_map.get(k, k), v))),
    )

question_type_map = {
    'tf': 'true_false_question',
    'mc': 'multiple_choice_question',
    'ma': 'multiple_answers_question',
    'match': 'matching_question',
    'mat': 'matching_question',
    'sa': 'short_answer_question',
    'e': 'essay_question',
    'u': 'file_upload_question',
}

def map_question_type(question: dict):
    if 'question_type' in question:
        q_type = question['question_type']
        return assoc(
            question, 'question_type',
            question_type_map.get(q_type, q_type)
        )
    return question

@curry
def process_question(course: Course, course_root: str, question: dict):
    question = pipe(
        question,
        map_question_keys,
        map_question_type,
    )

    if 'question_text' not in question:
        log.error(
            f'Question missing question_text:\n{pprint_question(question)}'
        )
        return Null

    question['question_text'] = str(templates.common.render_markdown_content(
        course, course_root, question['question_text']
    ))
    
    def needs_answers(question):
        return question.get('question_type') not in {
            'file_upload_question', 'short_answer_question',
            'essay_question',
        }

    if not needs_answers(question):
        return question

    if 'answers' not in question:
        log.error(
            f'Question missing answers:\n{pprint_question(question)}'
        )
        return Null

    answers = [process_answer(course, course_root, a)
               for a in question['answers']]

    if not all(answers):
        return Null

    if 'question_type' not in question:
        n_correct_answers = sum(
            1 if a['answer_weight'] else 0 for a in answers
        )
        if n_correct_answers > 1:
            question['question_type'] = 'multiple_answers_question'
        else:
            question['question_type'] = 'multiple_choice_question'

    return merge(
        question,
        {'answers': answers},
    )

@curry
def process_quiz(course: Course, course_root: str, quiz: dict):
    rng = random.Random(course_id_tuple(course))

    if 'title' not in quiz:
        log.error('Quiz does not have a title')
        return Null

    if 'questions' not in quiz:
        log.error('Quiz does not have questions')
        return Null

    questions = quiz['questions']
    if quiz.get('shuffle_questions'):
        questions = rng.sample(questions, len(questions))

    questions = [process_question(course, course_root, q) for q in questions]
    if not all(questions):
        return Null
        
    return merge(
        pipe(
            quiz,
            remove_keys(['shuffle_questions']),
        ),
        {'questions': questions},
        {'description': str(templates.common.render_markdown_content(
            course, course_root, quiz['description']
        ))},
    )

@curry
def find_quiz(course: Course, title: str):
    for q in quizzes(course, do_memo=False):
        if q.data['title'] == title:
            return q

def create_quiz(course: Course, quiz_data: dict):
    # Split quiz and question data
    quiz_data = dissoc(quiz_data, 'questions')
    quiz_hash = common.hash_from_dict(quiz_data)

    # Need to create a new quiz
    log.info(
        f'[create_quiz] Creating new quiz:'
        f' "{quiz_data["title"]}"'
    )
    quiz_ep = new_quiz(course, quiz_data)
    # Set the metadata (i.e. hash of quiz metadata) for the new
    # quiz
    set_metadata(
        quiz_ep, {
            'hash': quiz_hash,
            'questions': {'hashes': []},
        }
    )
    return quiz_ep

def update_quiz(course: Course, quiz_data: dict):
    # Split quiz and question data
    quiz_data = dissoc(quiz_data, 'questions')
    quiz_hash = common.hash_from_dict(quiz_data)

    log.info(
        '[update_quiz] Checking quiz metadata...'
    )
    quiz_ep = find_quiz(course, quiz_data['title'])

    # Pull quiz metadata (quiz hash and question hashes)
    quiz_md = get_metadata(quiz_ep)

    # Check the stored hash of quiz data to see if something has
    # changed
    if quiz_md.get('hash') != quiz_hash:
        log.info(
            '[update_quiz] ... quiz metadata has changed. Updating endpoint.'
        )
        quiz_ep = update_endpoint(quiz_ep, quiz_data)
        set_metadata(
            quiz_ep, merge(
                quiz_md, {'hash': quiz_hash},
            )
        )
    else:
        log.info(
            '[update_quiz] ... no change to quiz metadata.'
        )

    return quiz_ep

def create_questions(course: Course, quiz_data: dict):
    '''Ok, so...

    We have to destroy/recreate the questions because something weird
    happens when we do a PUT on an individual QuizQuestion object. So,
    we can't do spot-updates on existing questions.

    Yay.

    '''
    quiz_ep = find_quiz(course, quiz_data['title'])
    log.info(
        f"[create_questions] Pulling question data for quiz:"
        f" {quiz_data['title']} ..."
    )
    question_eps = questions(quiz_ep)
    question_data = quiz_data['questions']

    quiz_md = get_metadata(quiz_ep)
    question_md = quiz_md['questions']
    question_hashes = pipe(
        question_data,
        map(common.hash_from_dict),
        tuple,
    )
    
    if all(a == b for a, b in itertools.zip_longest(
            question_hashes, question_md['hashes'])):
        log.info(
            '[create_questions] ... no differences detected in the questions.'
        )
        return question_eps

    if question_eps:
        log.info(
            '[create_questions] ... questions differ.. deleting'
            f' {len(question_eps)} existing questions.'
        )
    for q_ep in question_eps:
        q_ep.delete()

    log.info(
        '[create_questions] Creating new questions'
    )
    question_eps = [
        new_question(quiz_ep, q_data) for q_data in question_data
    ]
    quiz_md['questions']['hashes'] = question_hashes
    set_metadata(quiz_ep, quiz_md)

    log.info(
        f'[create_questions] Updating question count: {len(question_data)}'
    )
    update_endpoint(quiz_ep, {'question_count': len(question_data)})
    return question_eps

def quiz_data_from_yaml(course: Course, course_root: str,
                        path: Union[str, Path]):
    '''For a given Course Endpoint, whose root directory is course_root,
    and for a particular quiz configuration (templated YAML) at path,
    return the dictionary representation of that quiz.

    '''
    return pipe(
        templates.common.render_yaml_path(course, course_root, path),
        process_quiz(course, course_root),
    )

@curry
def sync_quiz_from_path(course: Course, course_root: Union[str, Path],
                        path: Union[str, Path]):
    '''For a given Course Endpoint (course), root directory path
    (course_root), and path to quiz YAML (path), return
    created/modified Quiz Endpoint object.

    Args:

      course (Endpoint): Course Endpoint object to which this quiz
        should be added

      course_root (Union[str, Path]): Path to the course root
        directory. This will be the root path that all relative paths
        in the quiz YAML will build off of (e.g. the `questions`
        template function use to include other quiz YAML data).

      path (Union[str, Path]): Path to the quiz YAML file to be
        loaded.

    Returns: Quiz Endpoint object for this created/modified quiz

    '''
    quiz_data = quiz_data_from_yaml(course, course_root, path)
    group_ep = maybe_pipe(
        quiz_data.pop('assignment_group', None),
        assignment.find_assignment_group(course),
    )
    if group_ep:
        quiz_data['assignment_group_id'] = group_ep.data['id']

    if not quiz_data:
        return Null

    quiz = (find_quiz(course, quiz_data['title']) or
            create_quiz(course, quiz_data))
    if quiz:
        quiz = update_quiz(course, quiz_data)
        if quiz:
            questions = create_questions(course, quiz_data)

    return quiz

@curry
def sync_quizzes_from_path(course: IdResourceEndpoint, course_root: str,
                           quizzes_root: str):
    return pipe(
        Path(quizzes_root).expanduser().glob('quiz-*.yml'),
        pmap(sync_quiz_from_path(course, course_root), max_workers=5),
        tuple,
    )
