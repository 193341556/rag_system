from locust import HttpUser, task, between

class RAGUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    doc_id = None

    def on_start(self):
        # 登录拿 token
        resp = self.client.post('/api/auth/login',
            json={'username': 'loadtest', 'password': 'loadtest'})
        if resp.status_code == 200:
            self.token = resp.json()['access_token']
            self.headers = {'Authorization': f'Bearer {self.token}'}
        else:
            # 用户不存在则先注册
            self.client.post('/api/auth/register',
                json={'username': 'loadtest', 'password': 'loadtest'})
            resp = self.client.post('/api/auth/login',
                json={'username': 'loadtest', 'password': 'loadtest'})
            self.token = resp.json()['access_token']
            self.headers = {'Authorization': f'Bearer {self.token}'}

        # 拿第一个 ready 状态的文档
        resp = self.client.get('/api/documents/?status=ready',
            headers=self.headers)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            if items:
                self.doc_id = items[0]['task_id']

    @task(3)
    def ask_question(self):
        if not self.doc_id:
            return
        self.client.post(f'/api/chat/ask?doc_id={self.doc_id}&question=这篇文档的主要内容是什么',
            headers=self.headers)

    @task(1)
    def list_documents(self):
        self.client.get('/api/documents/', headers=self.headers)