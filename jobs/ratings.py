from hashlib import sha256


def rating_key(account):
    return sha256(account.encode('utf-8')).hexdigest()


def rating_summary(db, job_id, account=None):
    values = []
    own = None
    for document in db.collection('job_postings').document(job_id).collection('ratings').stream():
        value = document.to_dict().get('value')
        if type(value) is int and 1 <= value <= 5:
            values.append(value)
            if account and document.id == rating_key(account):
                own = value
    average = round(sum(values) / len(values), 1) if values else 0
    return {'rating_average': average, 'rating_count': len(values),
            'rating_width': average * 20, 'own_rating': own}
