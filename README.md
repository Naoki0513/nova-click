# nova-click

A browser automation agent that combines **Amazon Nova** model from Amazon Bedrock with Playwright to enable browser automation using natural language commands.

![Demo](assets/demo.gif)

---

## Why Nova?

Amazon Nova is ideal for browser automation with its fast processing speed and large context window. It efficiently understands extensive webpage data and smoothly executes natural language commands for browser operations.

---

## Quick Start

### 1. Prerequisites

#### 1.1. Creating an IAM User and Setting Permissions

1.  Sign in to the **AWS Management Console** and open the [IAM console](https://console.aws.amazon.com/iam/).
2.  In the navigation pane, choose **[Users]** and then click **[Add users]**.
3.  Enter a username and select **[Programmatic access]**.
4.  In the **[Permissions]** step, select **[Attach policies directly]**.
5.  Click **[Create policy]** to open the policy editor in a new tab.
6.  Select the **[JSON]** tab and paste the following policy:

    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockInvokeModel",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": "*"
            }
        ]
    }
    ```
7.  Give the policy a name (e.g., `BedrockInvokeAccess`) and save it.
8.  Return to the user creation tab, search for the policy you created, select it, and attach it.
9.  Add tags (optional) and complete the user creation.

For more detailed instructions, please refer to the official AWS documentation:
[Authenticating using IAM user credentials for the AWS CLI](https://docs.aws.amazon.com/cli/v1/userguide/cli-authentication-user.html#cli-authentication-user-create)

#### 1.2. Obtaining Access Keys

1.  Open the details page for the IAM user you created.
2.  Select the **[Security credentials]** tab.
3.  In the **[Access keys]** section, click **[Create access key]**.
4.  Select **[Command Line Interface (CLI)]** as the use case, check the confirmation checkbox, and proceed.
5.  Set a description tag (optional) and click **[Create access key]**.
6.  **Important:** Make sure to note down the **Access key ID** and **Secret access key** that are displayed. We strongly recommend clicking **[Download .csv file]** and storing it in a secure location. The secret access key will not be shown again once you close this screen.

#### 1.3. Saving Access Keys

1.  Create a `credentials` directory at the root of the repository (if it doesn't exist).
2.  Create a file named `aws_credentials.json` in the `credentials` directory.
3.  Save your access key information in `aws_credentials.json` using the following format. For `region_name`, specify the region where you'll be using Bedrock (e.g., `us-west-2`).

```json
{
  "aws_access_key_id": "YOUR_ACCESS_KEY_ID",
  "aws_secret_access_key": "YOUR_SECRET_ACCESS_KEY",
  "region_name": "us-west-2"
}
```

### 2. Installing Dependencies

```bash
pip install boto3==1.38.13
pip install playwright==1.40.0
python -m playwright install chromium
```

### 3. Execution

```bash
python main.py
```

By default, the prompt "Search for the most popular waterproof Bluetooth speaker under $50 on Amazon and add it to the cart" will be executed. If you want to change the settings, edit the constants at the beginning of `main.py`.

### 4. Supported Models

This agent supports multiple models from Amazon Bedrock and Anthropic:

- **Amazon Nova Pro** (default): `us.amazon.nova-pro-v1:0`
- **Amazon Nova Premier**: `us.amazon.nova-premier-v1:0`
- **Amazon Nova Lite**: `us.amazon.nova-lite-v1:0`
- **Claude 3.7 Sonnet**: `anthropic.claude-3-7-sonnet-20250219`

You can change the model by modifying the `DEFAULT_MODEL_ID` constant in `main.py`.