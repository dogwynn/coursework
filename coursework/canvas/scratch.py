def create_questions(course: Course, quiz_data: dict):
    quiz_ep = find_quiz(course, quiz_data['title'])
    question_data = quiz_data['questions']

    # Get the quiz metadata stored in Canvas (via custom_data
    # API). This contains the question metadata (i.e. hashes of
    # question data). If there are additional questions, then we
    # will have to update the quiz metadata at the end.
    quiz_md = get_metadata(quiz_ep)
    # hashes => {hash: quiz id}
    question_md = quiz_md['questions']
    log.info(f'quiz_md: {quiz_md}')

    # {hash: question data dictionary}
    question_hashes = OrderedDict([
        (common.hash_from_dict(q), q) for q in question_data
    ])

    question_eps = questions(quiz_ep)

    def find_question(q_id):
        return pipe(
            question_eps,
            filter(lambda ep: ep.data['id'] == q_id),
            maybe_first,
        )

    # Hashes of Question objects currently stored in Canvas
    #
    # {hash: question endpoint}
    extant_hashes = pipe(
        question_md['hashes'].items(),
        vmap(lambda h, q_id: (h, find_question(q_id))),
        vfilter(lambda h, ep: ep),
        dict,
    )

    to_add = pipe(
        set(question_hashes) - set(extant_hashes),
        map(lambda h: (h, question_hashes.get(h))),
        tuple,
    )

    if to_add:
        # Create the Question objects in Canvas
        for q_hash, q_data in to_add:
            log.info(
                f'Creating question:\n{pprint_question(q_data)}'
            )
            new_q_ep = new_question(quiz_ep, q_data)
            question_md['hashes'][q_hash] = new_q_ep.data['id']

    to_remove = pipe(
        set(extant_hashes) - set(question_hashes),
        map(lambda h: (h, extant_hashes.get)),
        tuple,
    )

    if to_remove:
        # Question objects not needed any more
        for q_hash, q_ep in to_remove:
            log.info('Removing Question object:'
                     f' {q_ep.data["question_text"]}')
            outcome = q_ep.maybe_delete()
            if not outcome.ok:
                log.error(
                    'Error deleting Question object:\n'
                    f'{pprint_question(q_ep.data)}'
                )
                return False
            del question_md['hashes'][q_hash]

    set_metadata(quiz_ep, quiz_md)

    update_endpoint(quiz_ep, {'question_count': len(question_data)})

    return questions(quiz_ep)


def reorder_questions(course: Course, quiz_data: dict):
    quiz_ep = find_quiz(course, quiz_data['title'])
    question_data = quiz_data['questions']

    question_hashes = [
        (common.hash_from_dict(q), q) for q in question_data
    ]

    quiz_md = get_metadata(quiz_ep)
    question_md = quiz_md.setdefault('questions', {'hashes': {}})

    question_eps = questions(quiz_ep)

    def find_question(q_id):
        return pipe(
            question_eps,
            filter(lambda ep: ep.data['id'] == q_id),
            maybe_first,
        )

    extant_hashes = pipe(
        question_md['hashes'].items(),
        vmap(lambda h, q_id: (h, find_question(q_id))),
        vfilter(lambda h, ep: ep),
        dict,
    )

    for position, (q_hash, q_data) in enumerate(question_hashes, 1):
        log.info(
            f'[reorder_questions] Moving Question'
            f' ({q_data["question_text"][:100]}) to position {position}'
        )
        q_ep = extant_hashes.get(q_hash)
        if not q_ep:
            log.error('[reorder_questions] Could not move question,'
                      ' since it has not added to Canvas:\n'
                      f'{pprint_question(q_data)}')
            return False
        update_endpoint(q_ep, {'position': position}, do_refresh=False)

    return question_eps

