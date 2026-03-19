#parameters involved for recommendation engine:
#1. Submissions: an their tags, look for those tags that are highly occuring in cf but the user has not solved many problems in those tags.
#2. Contests: for for the contests the user has given and then look for scope of upsolving one problem
#3. Rating: use the problem_list for each rating class and take some problems from there also

from cf_api import CodeforcesAPI


api=CodeforcesAPI()



def process_submissions(submissions):
    tag_count = {}
    for submission in submissions:
        if submission['verdict'] == 'OK':  # Only consider solved problems
            for tag in submission['problem']['tags']:
                tag_count[tag] = tag_count.get(tag, 0) + 1
    return tag_count


def problem_recommendations(handle):
    user_data = api.get_user_data(handle)
    submissions = user_data['submissions']
    upsolve_list = user_data['upsolve_list']
    tag_count = process_submissions(submissions)
    
    # Sort tags by count and recommend problems from less solved tags
    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1])
    
    return {
        "upsolve_problems": upsolve_list,
        "tag_recommendations": sorted_tags 
    }