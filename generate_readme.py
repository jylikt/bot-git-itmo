import openai

def generate_readme(repo_name, repo_description, setup_instructions):
    prompt = f"# {repo_name}\n\n{repo_description}\n\n## Установка\n\n{setup_instructions}\n\n## Использование\n\n"  
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']
